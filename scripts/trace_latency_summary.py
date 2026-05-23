#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _records(paths: Iterable[Path]) -> Iterable[Dict[str, Any]]:
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if isinstance(record, dict):
                    yield record


def _duration(record: Dict[str, Any]) -> float:
    try:
        return float(record.get("duration_ms") or 0.0)
    except Exception:
        return 0.0


def _queue_wait(record: Dict[str, Any]) -> float:
    try:
        return float(record.get("queue_wait_ms") or 0.0)
    except Exception:
        return 0.0


def summarize(paths: List[Path]) -> str:
    spans: List[Dict[str, Any]] = []
    cumulative: Dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()
    queue_waits: List[Tuple[float, str, str]] = []
    static_plus_dynamic = 0
    tactical_count = 0
    tactical_total = 0.0
    dm_combat_count = 0
    dm_combat_total = 0.0
    dm_combat_max = 0.0
    ordinary_static: Counter[str] = Counter()
    over_1000: Counter[str] = Counter()
    over_5000: Counter[str] = Counter()
    ordinary_commands = {
        "move",
        "set_facing",
        "end_turn",
        "attack_request",
        "cast_spell",
        "cast_aoe",
        "manual_override_resource_pool",
        "reaction_prefs_update",
        "equip_inventory_item",
        "unequip_inventory_item",
        "monster_capability_execute",
    }

    for record in _records(paths):
        span = str(record.get("span") or record.get("function") or record.get("path") or "")
        event = str(record.get("event") or "")
        command = str(record.get("command") or "")
        duration = _duration(record)
        if duration > 0 and event == "span.end":
            spans.append(record)
            key = span or event or command or "unknown"
            cumulative[key] += duration
            counts[key] += 1
        if event == "lan.state.broadcast_completed" and record.get("broadcast_kind") == "static_plus_dynamic":
            static_plus_dynamic += 1
            if command in ordinary_commands:
                ordinary_static[command] += 1
        if event == "span.end" and (span == "_dm_tactical_snapshot" or record.get("function") == "_dm_tactical_snapshot"):
            tactical_count += 1
            tactical_total += duration
        path = str(record.get("path") or record.get("route") or record.get("url") or "")
        if event == "span.end" and ("/api/dm/combat" in path or command == "/api/dm/combat"):
            dm_combat_count += 1
            dm_combat_total += duration
            dm_combat_max = max(dm_combat_max, duration)
        wait = _queue_wait(record)
        if wait > 0 and event == "ws.action.dispatch.start":
            queue_waits.append((wait, command or "unknown", str(record.get("action_id") or "")))
            if wait > 1000:
                over_1000[command or "unknown"] += 1
            if wait > 5000:
                over_5000[command or "unknown"] += 1

    lines: List[str] = []
    lines.append("Top spans by duration:")
    for record in sorted(spans, key=_duration, reverse=True)[:30]:
        lines.append(f"  {_duration(record):10.3f} ms  {record.get('span') or record.get('function') or record.get('event')}  command={record.get('command') or ''}")
    lines.append("")
    lines.append("Top spans by cumulative duration:")
    for key, total in sorted(cumulative.items(), key=lambda item: item[1], reverse=True)[:30]:
        lines.append(f"  {total:10.3f} ms  count={counts[key]:5d}  {key}")
    lines.append("")
    lines.append("Top queue waits:")
    for wait, command, action_id in sorted(queue_waits, reverse=True)[:30]:
        lines.append(f"  {wait:10.3f} ms  {command}  {action_id}")
    lines.append("")
    lines.append(f"static_plus_dynamic builds: {static_plus_dynamic}")
    lines.append(f"_dm_tactical_snapshot calls: {tactical_count} cumulative_ms={tactical_total:.3f}")
    avg = dm_combat_total / dm_combat_count if dm_combat_count else 0.0
    lines.append(f"/api/dm/combat count={dm_combat_count} avg_ms={avg:.3f} max_ms={dm_combat_max:.3f} cumulative_ms={dm_combat_total:.3f}")
    lines.append(f"queue_wait_ms >1000 by command: {dict(over_1000)}")
    lines.append(f"queue_wait_ms >5000 by command: {dict(over_5000)}")
    lines.append(f"ordinary actions triggering static_plus_dynamic: {dict(ordinary_static)}")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if not argv:
        print("usage: scripts/trace_latency_summary.py logs/debug-trace-*.jsonl", file=sys.stderr)
        return 2
    paths = [Path(arg) for arg in argv]
    print(summarize(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

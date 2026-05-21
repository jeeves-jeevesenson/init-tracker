#!/usr/bin/env python3
"""Summarize opt-in init tracker live debug trace JSONL files."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


def load_events(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    events: List[Dict[str, Any]] = []
    stats = {"lines": 0, "bad_lines": 0, "non_object_lines": 0}
    try:
        handle = Path(path).open("r", encoding="utf-8")
    except FileNotFoundError:
        return events, stats
    with handle:
        for raw_line in handle:
            stats["lines"] += 1
            line = raw_line.strip()
            if not line:
                stats["bad_lines"] += 1
                continue
            try:
                payload = json.loads(line)
            except Exception:
                stats["bad_lines"] += 1
                continue
            if not isinstance(payload, dict):
                stats["non_object_lines"] += 1
                continue
            events.append(payload)
    return events, stats


def _duration(event: Dict[str, Any]) -> Optional[float]:
    raw = event.get("duration_ms")
    try:
        return float(raw)
    except Exception:
        return None


def _timestamp(event: Dict[str, Any]) -> Optional[datetime]:
    raw = str(event.get("ts") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _ms(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.3f} ms"


def _span_rows(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [event for event in events if event.get("event") == "span.end" and _duration(event) is not None]


def _mean(values: List[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _group_durations(
    events: Iterable[Dict[str, Any]],
    key_fn: Callable[[Dict[str, Any]], str],
) -> List[Tuple[str, int, float, float, float]]:
    grouped: Dict[str, List[float]] = defaultdict(list)
    for event in events:
        duration_ms = _duration(event)
        if duration_ms is None:
            continue
        grouped[key_fn(event)].append(duration_ms)
    rows = [
        (key, len(values), sum(values), _mean(values), max(values))
        for key, values in grouped.items()
        if values
    ]
    rows.sort(key=lambda row: (row[2], row[4], row[1]), reverse=True)
    return rows


def _append_group_section(
    lines: List[str],
    title: str,
    rows: List[Tuple[str, int, float, float, float]],
    *,
    limit: int = 20,
) -> None:
    lines.append("")
    lines.append(title)
    if not rows:
        lines.append("  no matching timing rows")
        return
    for key, count, total_ms, avg_ms, max_ms in rows[:limit]:
        lines.append(
            f"  {key}: count={count} total={total_ms:.3f} ms avg={avg_ms:.3f} ms max={max_ms:.3f} ms"
        )


def _slowest_spans(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = _span_rows(events)
    rows.sort(key=lambda event: _duration(event) or 0.0, reverse=True)
    return rows[:20]


def _action_rows(events: List[Dict[str, Any]]) -> List[Tuple[str, int, float, float, str]]:
    grouped: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"durations": [], "commands": set()})
    for event in _span_rows(events):
        action_id = _text(event.get("action_id"), "")
        if not action_id:
            continue
        grouped[action_id]["durations"].append(_duration(event) or 0.0)
        command = _text(event.get("command"), "")
        if command:
            grouped[action_id]["commands"].add(command)
    rows: List[Tuple[str, int, float, float, str]] = []
    for action_id, data in grouped.items():
        durations = list(data["durations"])
        commands = ",".join(sorted(data["commands"])) or "-"
        rows.append((action_id, len(durations), sum(durations), max(durations), commands))
    rows.sort(key=lambda row: (row[2], row[3], row[1]), reverse=True)
    return rows[:20]


def _matching_spans(events: List[Dict[str, Any]], needles: Iterable[str]) -> List[Dict[str, Any]]:
    wanted = tuple(str(needle).lower() for needle in needles)
    matches = []
    for event in _span_rows(events):
        searchable = " ".join(
            _text(event.get(key), "")
            for key in ("span", "command", "function", "event")
        ).lower()
        if any(needle in searchable for needle in wanted):
            matches.append(event)
    return matches


def _suspected_bottlenecks(events: List[Dict[str, Any]]) -> List[str]:
    candidates = [
        event
        for event in events
        if event.get("event") in {"hang_candidate.span", "very_slow.span", "slow.span"}
        and _duration(event) is not None
    ]
    candidates.sort(key=lambda event: _duration(event) or 0.0, reverse=True)
    if candidates:
        lines = []
        for event in candidates[:10]:
            lines.append(
                "  "
                + f"{_text(event.get('event'))} {_text(event.get('span'))}"
                + f" duration={_ms(_duration(event))}"
                + f" command={_text(event.get('command'))}"
                + f" action_id={_text(event.get('action_id'))}"
            )
        return lines
    slowest = _slowest_spans(events)
    if slowest:
        event = slowest[0]
        return [
            "  no slow-threshold event recorded; inspect the current slowest span "
            + f"{_text(event.get('span'))} at {_ms(_duration(event))}"
        ]
    return ["  no completed spans were recorded"]


def build_report(events: List[Dict[str, Any]], stats: Optional[Dict[str, int]] = None) -> str:
    stats = stats or {}
    timestamps = [stamp for stamp in (_timestamp(event) for event in events) if stamp is not None]
    session_ms = 0.0
    if len(timestamps) >= 2:
        session_ms = max(0.0, (max(timestamps) - min(timestamps)).total_seconds() * 1000.0)
    action_ids = {_text(event.get("action_id"), "") for event in events}
    action_ids.discard("")
    lines = [
        "Init Tracker Debug Trace Analysis",
        f"events: {len(events)}",
        f"input lines: {int(stats.get('lines', len(events)))}",
        f"ignored bad lines: {int(stats.get('bad_lines', 0)) + int(stats.get('non_object_lines', 0))}",
        f"total session duration: {_ms(session_ms)}",
        f"total actions: {len(action_ids)}",
    ]

    lines.append("")
    lines.append("Slowest 20 spans")
    slowest = _slowest_spans(events)
    if not slowest:
        lines.append("  no completed spans")
    for event in slowest:
        lines.append(
            "  "
            + f"{_ms(_duration(event))} span={_text(event.get('span'))}"
            + f" command={_text(event.get('command'))}"
            + f" route={_text(event.get('route'))}"
            + f" action_id={_text(event.get('action_id'))}"
        )

    lines.append("")
    lines.append("Slowest 20 user actions by action_id")
    action_rows = _action_rows(events)
    if not action_rows:
        lines.append("  no action-correlated spans")
    for action_id, count, total_ms, max_ms, commands in action_rows:
        lines.append(
            f"  {action_id}: spans={count} total={total_ms:.3f} ms max={max_ms:.3f} ms commands={commands}"
        )

    http_ends = [event for event in events if event.get("event") == "http.request.end"]
    _append_group_section(
        lines,
        "Route timing summary",
        _group_durations(http_ends, lambda event: f"{_text(event.get('method'))} {_text(event.get('route'))}"),
    )

    ws_ends = [event for event in events if event.get("event") == "ws.action.dispatch.end"]
    _append_group_section(
        lines,
        "Websocket action timing summary",
        _group_durations(ws_ends, lambda event: _text(event.get("command"))),
    )

    broadcast_ends = [event for event in events if event.get("event") == "broadcast.end"]
    _append_group_section(
        lines,
        "Broadcast summary",
        _group_durations(
            broadcast_ends,
            lambda event: f"{_text(event.get('span'))} {_text(event.get('command'))}",
        ),
    )

    _append_group_section(
        lines,
        "Snapshot build summary",
        _group_durations(
            _matching_spans(events, ("snapshot", "serialization")),
            lambda event: _text(event.get("span")),
        ),
    )

    _append_group_section(
        lines,
        "Spell/reaction summary",
        _group_durations(
            _matching_spans(events, ("spell", "cast", "reaction", "shield", "rebuke", "summon", "save")),
            lambda event: _text(event.get("span")),
        ),
    )

    _append_group_section(
        lines,
        "YAML/cache summary",
        _group_durations(
            _matching_spans(events, ("yaml", "cache")),
            lambda event: _text(event.get("span")),
        ),
    )

    _append_group_section(
        lines,
        "Top repeated expensive spans",
        _group_durations(_span_rows(events), lambda event: _text(event.get("span"))),
    )

    lines.append("")
    lines.append("Suspected bottlenecks")
    lines.extend(_suspected_bottlenecks(events))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Path to debug-trace JSONL output.")
    args = parser.parse_args(argv)
    events, stats = load_events(args.trace)
    print(build_report(events, stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

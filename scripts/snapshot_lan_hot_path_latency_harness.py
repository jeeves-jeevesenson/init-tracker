#!/usr/bin/env python3
"""Summarize snapshot/LAN hot-path latencies from debug-trace JSONL files.

Latency samples are taken from ``span.end`` events only. Existing trace
diagnostic events are counted separately so slow samples are not double-counted.

Percentiles use the deterministic nearest-rank method:
sort durations ascending, then select ``ceil(percentile / 100 * count)``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_THRESHOLDS_MS = (100.0, 250.0, 1000.0)
TARGET_SPANS = (
    "_lan_snapshot",
    "_dm_tactical_snapshot",
    "_dm_console_snapshot",
    "_dm_console_snapshot_payload",
    "_load_player_yaml_cache",
    "combat_service.combat_snapshot",
    "dm.console.route_read_snapshot",
    "dm.console.route_payload_proxy",
    "dm.console.snapshot.cache_check",
    "dm.console.snapshot.payload",
    "dm.console.combat_snapshot",
    "dm.console.combat_snapshot.service_call",
    "dm.console.combat_snapshot.copy",
    "dm.console.combat_snapshot.provided_copy",
    "dm.console.tactical_snapshot",
    "dm.console.tactical_snapshot.provided_copy",
    "dm.console.payload.tactical_merge",
    "dm.console.payload.pending_prompts",
    "dm.console.payload.size_proxy",
    "dm.tactical.from_lan_snapshot",
    "lan.snapshot.build",
    "lan.snapshot.map_window",
    "lan.snapshot.canonical_map",
    "lan.snapshot.aoes",
    "lan.snapshot.auras",
    "lan.snapshot.units",
    "lan.snapshot.tactical_payload",
    "lan.snapshot.static_fields",
    "lan.snapshot.resource_pools",
    "dm.console.threadpool_dispatch_queue",
    "dm.console.route_response_build",
)
HTTP_COMBAT_LABEL = "http.request:/api/dm/combat"
TARGET_LABELS = (*TARGET_SPANS, HTTP_COMBAT_LABEL)
DIAGNOSTIC_EVENTS = ("slow.span", "very_slow.span", "hang_candidate.span")
COUNT_KEYS = (
    "combatant_count",
    "player_count",
    "monster_count",
    "map_aoe_count",
    "pending_prompt_count",
    "pending_reaction_count",
    "websocket_client_count",
    "dm_websocket_client_count",
    "total_websocket_client_count",
)


def positive_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a positive number, got {raw!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive number, got {raw!r}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read existing init-tracker debug trace JSONL files and summarize "
            "snapshot/LAN hot-path latency spans. This does not start a server "
            "or mutate logs."
        )
    )
    parser.add_argument(
        "trace_paths",
        nargs="+",
        type=Path,
        help="one or more debug trace JSONL files",
    )
    parser.add_argument(
        "--slow-threshold-ms",
        action="append",
        type=positive_float,
        default=None,
        help=(
            "latency threshold to count as slow; repeat for multiple thresholds "
            f"(default: {', '.join(format_number(value) for value in DEFAULT_THRESHOLDS_MS)})"
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="optional path for a JSON summary",
    )
    return parser.parse_args()


def format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == int(value):
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}ms"


def threshold_key(value: float) -> str:
    return f">={format_number(value)}ms"


def duration_from(record: dict[str, object]) -> float | None:
    raw_duration = record.get("duration_ms")
    if isinstance(raw_duration, (int, float)):
        return float(raw_duration)
    if isinstance(raw_duration, str):
        try:
            return float(raw_duration)
        except ValueError:
            return None
    return None


def low_cardinality_context(record: dict[str, object]) -> str | None:
    raw_context = record.get("snapshot_caller", record.get("scope"))
    if not isinstance(raw_context, str):
        return None
    context = raw_context.strip().lower().replace("-", "_")
    if not context:
        return None
    return context[:80]


def numeric_count(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def merge_max_counts(max_counts: dict[str, int], record: dict[str, object]) -> None:
    raw_counts = record.get("counts")
    if not isinstance(raw_counts, dict):
        return
    for key in COUNT_KEYS:
        value = numeric_count(raw_counts.get(key))
        if value is None:
            continue
        max_counts[key] = max(max_counts.get(key, 0), value)


def combat_route_matches(record: dict[str, object]) -> bool:
    route = record.get("route", record.get("path"))
    return record.get("span") == "http.request" and route == "/api/dm/combat"


def target_label(record: dict[str, object]) -> str | None:
    span = record.get("span")
    if span in TARGET_SPANS:
        return str(span)
    if combat_route_matches(record):
        return HTTP_COMBAT_LABEL
    return None


def empty_target_summary(thresholds_ms: tuple[float, ...]) -> dict[str, object]:
    return {
        "durations_ms": [],
        "duration_parse_failures": 0,
        "diagnostic_event_counts": {event: 0 for event in DIAGNOSTIC_EVENTS},
        "threshold_counts": {threshold_key(threshold): 0 for threshold in thresholds_ms},
        "contexts": {},
    }


def empty_context_summary() -> dict[str, object]:
    return {
        "durations_ms": [],
        "max_counts": {},
    }


def nearest_rank(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = ((percentile * len(sorted_values) + 99) // 100) - 1
    if index < 0:
        index = 0
    if index >= len(sorted_values):
        index = len(sorted_values) - 1
    return sorted_values[index]


def summarize_durations(
    durations_ms: list[float],
    thresholds_ms: tuple[float, ...],
) -> dict[str, object]:
    threshold_counts = {
        threshold_key(threshold): sum(1 for duration in durations_ms if duration >= threshold)
        for threshold in thresholds_ms
    }
    return {
        "count": len(durations_ms),
        "min_ms": min(durations_ms) if durations_ms else None,
        "p50_ms": nearest_rank(durations_ms, 50),
        "p95_ms": nearest_rank(durations_ms, 95),
        "max_ms": max(durations_ms) if durations_ms else None,
        "threshold_counts": threshold_counts,
    }


def read_trace_file(
    path: Path,
    targets: dict[str, dict[str, object]],
    thresholds_ms: tuple[float, ...],
) -> dict[str, object]:
    file_summary = {
        "path": str(path),
        "valid_json_objects": 0,
        "blank_lines": 0,
        "malformed_or_non_object_lines": 0,
    }
    with path.open("r", encoding="utf-8") as trace_file:
        for raw_line in trace_file:
            line = raw_line.strip()
            if not line:
                file_summary["blank_lines"] += 1
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                file_summary["malformed_or_non_object_lines"] += 1
                continue
            if not isinstance(record, dict):
                file_summary["malformed_or_non_object_lines"] += 1
                continue

            file_summary["valid_json_objects"] += 1
            label = target_label(record)
            if label is None:
                continue

            event = record.get("event")
            target = targets[label]
            if event == "span.end":
                duration_ms = duration_from(record)
                if duration_ms is None:
                    target["duration_parse_failures"] += 1
                    continue
                target["durations_ms"].append(duration_ms)
                context = low_cardinality_context(record)
                if context is not None:
                    contexts = target["contexts"]
                    if not isinstance(contexts, dict):
                        contexts = {}
                        target["contexts"] = contexts
                    context_target = contexts.setdefault(context, empty_context_summary())
                    context_target["durations_ms"].append(duration_ms)
                    merge_max_counts(context_target["max_counts"], record)
            elif event in DIAGNOSTIC_EVENTS:
                target["diagnostic_event_counts"][event] += 1

    for label in TARGET_LABELS:
        target = targets[label]
        target["threshold_counts"] = summarize_durations(
            target["durations_ms"], thresholds_ms
        )["threshold_counts"]
    return file_summary


def build_summary(
    trace_paths: list[Path],
    thresholds_ms: tuple[float, ...],
) -> dict[str, object]:
    targets = {
        label: empty_target_summary(thresholds_ms)
        for label in TARGET_LABELS
    }
    file_summaries = [
        read_trace_file(path, targets, thresholds_ms)
        for path in trace_paths
    ]

    target_summaries: dict[str, dict[str, object]] = {}
    for label in TARGET_LABELS:
        target = targets[label]
        duration_summary = summarize_durations(target["durations_ms"], thresholds_ms)
        target_summaries[label] = {
            **duration_summary,
            "duration_parse_failures": target["duration_parse_failures"],
            "diagnostic_event_counts": target["diagnostic_event_counts"],
            "contexts": {
                str(context): {
                    **summarize_durations(context_data["durations_ms"], thresholds_ms),
                    "max_counts": context_data["max_counts"],
                }
                for context, context_data in sorted(
                    target["contexts"].items(),
                    key=lambda item: (str(item[0]), len(item[1]["durations_ms"])),
                )
            },
        }

    return {
        "input_files": file_summaries,
        "thresholds_ms": list(thresholds_ms),
        "percentile_method": "nearest-rank over sorted span.end durations",
        "targets": target_summaries,
        "totals": {
            "valid_json_objects": sum(
                int(summary["valid_json_objects"]) for summary in file_summaries
            ),
            "blank_lines": sum(int(summary["blank_lines"]) for summary in file_summaries),
            "malformed_or_non_object_lines": sum(
                int(summary["malformed_or_non_object_lines"])
                for summary in file_summaries
            ),
        },
    }


def print_summary(summary: dict[str, object]) -> None:
    totals = summary["totals"]
    print("Snapshot/LAN hot-path latency summary")
    print("Inputs:")
    for file_summary in summary["input_files"]:
        print(
            f"  {file_summary['path']} "
            f"valid_json_objects={file_summary['valid_json_objects']} "
            f"blank_lines={file_summary['blank_lines']} "
            f"malformed_or_non_object_lines={file_summary['malformed_or_non_object_lines']}"
        )
    print(
        "Totals: "
        f"valid_json_objects={totals['valid_json_objects']} "
        f"blank_lines={totals['blank_lines']} "
        f"malformed_or_non_object_lines={totals['malformed_or_non_object_lines']}"
    )
    print(f"Percentiles: {summary['percentile_method']}")
    thresholds = [threshold_key(value) for value in summary["thresholds_ms"]]
    print(f"Slow thresholds: {', '.join(thresholds)}")
    print("")

    headers = [
        "target",
        "count",
        "min",
        "p50",
        "p95",
        "max",
        *thresholds,
        "trace_slow",
        "trace_very_slow",
        "trace_hang",
        "bad_duration",
    ]
    print(" ".join(headers))
    for label, target in summary["targets"].items():
        diagnostic_counts = target["diagnostic_event_counts"]
        threshold_counts = target["threshold_counts"]
        row = [
            label,
            str(target["count"]),
            format_ms(target["min_ms"]),
            format_ms(target["p50_ms"]),
            format_ms(target["p95_ms"]),
            format_ms(target["max_ms"]),
            *(str(threshold_counts[threshold]) for threshold in thresholds),
            str(diagnostic_counts["slow.span"]),
            str(diagnostic_counts["very_slow.span"]),
            str(diagnostic_counts["hang_candidate.span"]),
            str(target["duration_parse_failures"]),
        ]
        print(" ".join(row))

    context_rows = []
    for label, target in summary["targets"].items():
        contexts = target.get("contexts")
        if not isinstance(contexts, dict):
            continue
        for context, context_summary in contexts.items():
            if not isinstance(context_summary, dict):
                continue
            if not context_summary.get("count"):
                continue
            max_counts = context_summary.get("max_counts")
            if not isinstance(max_counts, dict):
                max_counts = {}
            context_rows.append(
                [
                    label,
                    str(context),
                    str(context_summary["count"]),
                    format_ms(context_summary["p50_ms"]),
                    format_ms(context_summary["p95_ms"]),
                    format_ms(context_summary["max_ms"]),
                    *(str(max_counts.get(key, 0)) for key in COUNT_KEYS),
                ]
            )
    print("")
    print("Caller/context breakdown:")
    if not context_rows:
        print("  No caller/context labels found in these traces.")
        return
    headers = [
        "target",
        "context",
        "count",
        "p50",
        "p95",
        "max",
        *COUNT_KEYS,
    ]
    print(" ".join(headers))
    for row in context_rows:
        print(" ".join(row))


def validate_inputs(paths: list[Path]) -> bool:
    missing_paths = [path for path in paths if not path.is_file()]
    if not missing_paths:
        return True
    for path in missing_paths:
        print(f"error: input file does not exist or is not a file: {path}", file=sys.stderr)
    return False


def write_json_summary(summary: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, indent=2, sort_keys=True)
        output_file.write("\n")


def main() -> int:
    args = parse_args()
    if not validate_inputs(args.trace_paths):
        return 2

    thresholds = args.slow_threshold_ms
    thresholds_ms = tuple(
        sorted(set(thresholds if thresholds is not None else DEFAULT_THRESHOLDS_MS))
    )
    summary = build_summary(args.trace_paths, thresholds_ms)
    print_summary(summary)
    if args.json_output is not None:
        write_json_summary(summary, args.json_output)
        print(f"\nJSON summary: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

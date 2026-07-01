# Snapshot/LAN Hot-Path Latency Measurement - 2026-07-01

## Command

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-155344.jsonl
```

## Summary Output

```text
Snapshot/LAN hot-path latency summary
Inputs:
  logs/debug-trace-20260701-155344.jsonl valid_json_objects=37486 blank_lines=0 malformed_or_non_object_lines=0
Totals: valid_json_objects=37486 blank_lines=0 malformed_or_non_object_lines=0
Percentiles: nearest-rank over sorted span.end durations
Slow thresholds: >=100ms, >=250ms, >=1000ms

target count min p50 p95 max >=100ms >=250ms >=1000ms trace_slow trace_very_slow trace_hang bad_duration
_lan_snapshot 2118 0.247ms 90.765ms 524.684ms 25282.205ms 1054 967 17 924 128 2 0
_dm_tactical_snapshot 177 4.010ms 49.390ms 1005.679ms 1357.979ms 80 47 10 33 47 0 0
_dm_console_snapshot 202 0.092ms 70.290ms 1020.172ms 1395.289ms 85 48 15 38 47 0 0
_dm_console_snapshot_payload 222 0.441ms 68.878ms 1018.191ms 1394.707ms 85 48 14 38 47 0 0
_load_player_yaml_cache 14170 0.079ms 0.113ms 0.293ms 25199.472ms 11 1 1 10 0 1 0
lan.snapshot.build 25 3.394ms 47.385ms 880.831ms 957.357ms 12 12 0 4 8 0 0
http.request:/api/dm/combat 176 1.958ms 98.701ms 1048.359ms 1404.445ms 87 47 14 41 46 0 0
```

## Repeated Slow Spans

`_lan_snapshot` slow spans are repeated in this trace.

The harness found `2118` `_lan_snapshot` `span.end` samples, p95 `524.684 ms`, max `25282.205 ms`, `1054` samples at or above `100 ms`, `967` at or above `250 ms`, and `17` at or above `1000 ms`. The trace also contained `924` `_lan_snapshot` `slow.span` diagnostics, `128` `very_slow.span` diagnostics, and `2` hang-candidate diagnostics.

Related hot-path targets also show repeated high-latency samples, especially `_dm_tactical_snapshot`, `_dm_console_snapshot`, `_dm_console_snapshot_payload`, and `http.request:/api/dm/combat`.

## Implementation Readiness

This evidence is sufficient to prove repeated snapshot/LAN hot-path latency in the named trace.

It is not sufficient for implementation. The trace is still one mixed smoke run with startup, browser WebSocket activity, workspace reads, LAN broadcasts, cache activity, claim/reconnect behavior, and game-state changes. The harness makes future comparison easier, but this first measurement does not isolate whether the next safe intervention would be cache ownership, TTL, snapshot schema, offload, route changes, payload changes, or something else.

## Recommended Next Action

Do not start latency implementation from this report.

If latency work continues, open a bounded controlled evidence/planning checkpoint that uses this harness against deliberately captured traces and decides whether a narrow implementation candidate exists. If deploy-prep review is higher priority, pausing latency work remains acceptable.

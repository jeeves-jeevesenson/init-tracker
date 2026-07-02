# Snapshot/LAN Hot-Path Controlled Evidence - 2026-07-01

## Evidence Inputs

Smoke log:

`logs/smoke/WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint_smoke-server_20260701-191158.log`

Debug trace:

`logs/debug-trace-20260701-191158.jsonl`

The smoke passed by developer report. A small bug was observed and intentionally deferred; it was not patched by this checkpoint.

## Controlled Smoke Facts

The smoke log records:

- Headless tracker started.
- Debug trace path: `logs/debug-trace-20260701-191158.jsonl`.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN session connected.
- Claim/unclaim flows for Dorian, Old Man, Johnny Morris, Throat Goat, and John Twilight.
- Attack weapon resolution for John Twilight.

## Harness Command

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-191158.jsonl
```

## Harness Output

```text
Snapshot/LAN hot-path latency summary
Inputs:
  logs/debug-trace-20260701-191158.jsonl valid_json_objects=37661 blank_lines=0 malformed_or_non_object_lines=0
Totals: valid_json_objects=37661 blank_lines=0 malformed_or_non_object_lines=0
Percentiles: nearest-rank over sorted span.end durations
Slow thresholds: >=100ms, >=250ms, >=1000ms

target count min p50 p95 max >=100ms >=250ms >=1000ms trace_slow trace_very_slow trace_hang bad_duration
_lan_snapshot 1075 0.235ms 98.260ms 1220.955ms 24704.439ms 489 435 80 373 105 11 0
_dm_tactical_snapshot 55 140.465ms 1197.004ms 2313.119ms 2536.769ms 55 47 41 14 36 5 0
_dm_console_snapshot 79 0.145ms 1212.072ms 2376.749ms 2638.671ms 61 57 41 17 39 5 0
_dm_console_snapshot_payload 99 0.437ms 323.099ms 2224.006ms 2638.226ms 73 57 41 29 39 5 0
_load_player_yaml_cache 16025 0.078ms 0.161ms 0.449ms 26578.796ms 6 1 1 5 0 1 0
lan.snapshot.build 31 5.130ms 426.811ms 1433.860ms 2037.209ms 22 19 2 17 4 1 0
http.request:/api/dm/combat 53 8.077ms 1326.809ms 2858.221ms 2941.737ms 51 51 37 10 38 3 0
```

## Interpretation

This controlled run confirms repeated material snapshot/LAN latency:

- `_lan_snapshot` has repeated slow and very-slow samples, including `80` samples at or above `1000 ms`.
- DM tactical and DM-console snapshot paths have p50 values around `1.2 s` and p95 values above `2.3 s`.
- `/api/dm/combat` is route-visible in the same controlled trace, with p50 `1326.809 ms`, p95 `2858.221 ms`, and max `2941.737 ms`.
- `lan.snapshot.build` also appears as a repeated contributor, with p50 `426.811 ms` and p95 `1433.860 ms`.
- The trace was parse-clean for the harness: malformed or non-object JSONL lines `0`.

The evidence is sufficient to justify a snapshot/LAN latency planning/design checkpoint. It is not sufficient to justify direct implementation because it does not identify the smallest safe code lever.

## Recommended Next Action

Open `WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint` only if the developer wants to continue latency work.

Do not start implementation, optimization, targeted app instrumentation, cache/TTL/schema/payload changes, route movement, WebSocket/queue changes, launch/readiness/shutdown changes, production operations, or gameplay changes from this report alone.

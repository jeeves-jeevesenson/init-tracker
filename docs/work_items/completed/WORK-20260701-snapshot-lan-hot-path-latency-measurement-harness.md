# WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness

Status: Completed

## Goal

Add a bounded developer-run measurement harness for snapshot/LAN hot-path latency using existing debug-trace JSONL files.

This was a Codex tooling/evidence slice only. It did not change app behavior, app code, tests, logs, route registration, route bodies, launch commands, lifespan behavior, readiness behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, TTLs, snapshot schemas, response payloads, static hydration, WebSocket behavior, auth/claims/reconnect, queue behavior, command semantics, persistence, shutdown semantics, production topology, deploys, restarts, SSH, pushes, commits, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_wait_evidence_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_smoke_evidence_capture_20260701.md`
- `logs/debug-trace-20260701-155344.jsonl`, using only `head`, `tail`, and `grep`
- `scripts/server_responsiveness_harness.py`

No app source, tests, browser assets, production files, old plans, old runtime reports, `majorTODO.md`, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected or edited.

## Files Changed

- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_measurement_harness_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_latency_measurement_20260701.md`

No active work item copy was left after completion.

## Harness Added

`scripts/snapshot_lan_hot_path_latency_harness.py` is a standard-library debug-trace JSONL parser.

It accepts one or more positional trace paths, fails clearly if an input path is missing, skips malformed or non-object JSONL lines with a warning count, and summarizes these targets from `span.end` duration samples:

- `_lan_snapshot`
- `_dm_tactical_snapshot`
- `_dm_console_snapshot`
- `_dm_console_snapshot_payload`
- `_load_player_yaml_cache`
- `lan.snapshot.build`
- `http.request` for `/api/dm/combat`

It reports count, min, p50, p95, max, threshold counts for configurable slow thresholds, and trace diagnostic counts for `slow.span`, `very_slow.span`, and `hang_candidate.span`. Percentiles use deterministic nearest-rank ordering over sorted `span.end` durations. Optional `--json-output` writes the same summary as JSON.

## Measurement Evidence

Command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-155344.jsonl
```

Summary:

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

## Decision

`_lan_snapshot` slow spans are repeated in this trace. The strongest harness numbers are `2118` `_lan_snapshot` samples, p95 `524.684 ms`, max `25282.205 ms`, `1054` samples at or above `100 ms`, `967` at or above `250 ms`, and `17` at or above `1000 ms`. Trace diagnostics separately recorded `924` `_lan_snapshot` `slow.span` events, `128` `very_slow.span` events, and `2` hang candidates.

The evidence is still not sufficient for implementation. The measurement summarizes one existing mixed smoke trace with startup activity, browser/WebSocket activity, workspace reads, broadcast work, cache activity, claim/reconnect behavior, and game-state changes. It proves repeated hot-path latency exists, but does not isolate the safest intervention.

Do not proceed directly to cache, offload, schema, payload, route, TTL, WebSocket, queue, launch, readiness, shutdown, production, or gameplay implementation from this evidence.

## Recommended Next Action

If latency work continues, the next work item should be a bounded controlled evidence/planning checkpoint using this harness across one or more intentionally captured traces. That checkpoint should decide whether a narrow implementation candidate exists.

If latency work is not required before deploy-prep review, pausing latency work remains acceptable.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this work item. The allowed next action is deploy-prep review, pause/no further migration, or a bounded snapshot/LAN controlled evidence/planning checkpoint if the developer wants to continue latency work.

## Validation

Required validation commands:

- `.venv/bin/python -m py_compile scripts/snapshot_lan_hot_path_latency_harness.py`
- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-155344.jsonl`
- `timeout 10s git diff --check`
- `git status --short`

Results are recorded in the final agent report.

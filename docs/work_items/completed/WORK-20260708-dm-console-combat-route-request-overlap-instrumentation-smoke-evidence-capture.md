# WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture

Status: Completed

## Goal

Open and complete a bounded smoke evidence checkpoint for commit `a01c398`.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation.md`
- `logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture_smoke-server_20260708-162049.log`
- `logs/debug-trace-20260708-162049.jsonl`
- `scripts/snapshot_lan_hot_path_latency_harness.py`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_instrumentation_smoke_evidence_capture_20260708.md`
- `docs/runtime_reports/dm_console_combat_route_request_overlap_instrumentation_smoke_evidence_20260708.md`

## Evidence Capture

The smoke proves that headless startup, debug trace creation, `/dm` and `/` advertisement, LAN server hoisting on port 8787, browser LAN session connection/disconnection, and Dorian claim flows still work.

The harness parsed `28,217` valid JSON objects and `0` malformed/non-object lines under a `112`-combatant / `102`-monster shape.

- `dm.console.threadpool_dispatch_queue` count=6 p50=0.350ms p95=88.188ms max=88.188ms.
- `dm.console.route_response_build` count=6 p50=0.389ms p95=0.429ms max=0.429ms.
- `http.request:/api/dm/combat` count=6 p50=331.813ms p95=1531.532ms max=1531.532ms.
- `dm.console.route_read_snapshot` count=6 p50=299.477ms p95=1492.095ms max=1492.095ms.

Keep commit `a01c398`. Recommended next work item is `WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint-followup` as a planning / evidence checkpoint to address the remaining gap between the HTTP route completion and the internal console snapshot read execution (potentially event-loop contention or concurrency overlaps).

## Validation

All required validation commands were executed successfully:
- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-162049.jsonl`
- `timeout 10s git diff --check`
- `git status --short`

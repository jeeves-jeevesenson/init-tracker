# WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint-followup

Status: Completed

## Goal

Open and complete a bounded follow-up planning/evidence checkpoint after route/request-overlap instrumentation smoke was accepted at commit `7155e7b`.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture.md`
- `docs/runtime_reports/dm_console_combat_route_request_overlap_instrumentation_smoke_evidence_20260708.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_instrumentation_smoke_evidence_capture_20260708.md`
- `logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture_smoke-server_20260708-162049.log`
- `logs/debug-trace-20260708-162049.jsonl`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_planning_checkpoint_followup_20260708.md`
- `docs/runtime_reports/dm_console_combat_route_request_overlap_planning_followup_20260708.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint-followup.md`

## Summary of Decisions

1. **Keep Commits `7155e7b` and `a01c398`**: Accepted. The new instrumentation successfully isolated latency details.
2. **Attribution of 1.5s HTTP Max**: Isolated the gap to **event-loop starvation / contention**. Under concurrent write load (POST `/api/dm/combat/start`), the synchronous state broadcast blocked the main thread for over 1.2s, causing the resumed GET `/api/dm/combat` coroutine to wait `715 ms` after completing its threadpool task.
3. **No Direct Route Implementation**: Route response serialization (`dm.console.route_response_build`) is ruled out (max `0.429 ms`). Threadpool queue delay is a watch item (max `88.188 ms`). With a sample size of only 6 GET requests, direct code implementation is not authorized.
4. **Next Recommended Work Item**: Controlled repeat evidence under `WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence` to gather 30+ requests during active combat operations over a dense 5-minute window.
5. **Deferred & Closed Elements**: Startup static fields and the small smoke bug remain deferred. Resource-pools remains closed. No app code or schemas changed.

## Validation

Executed:
- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-162049.jsonl`
- `timeout 10s git diff --check`
- `git status --short`
All validations passed successfully.

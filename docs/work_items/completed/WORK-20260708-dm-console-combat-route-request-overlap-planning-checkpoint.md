# WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint

Status: Completed

## Goal

Open and complete a bounded planning/evidence checkpoint for the remaining route-visible `/api/dm/combat` latency after composition refinement commit `82b996a` was kept.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture.md`
- `docs/runtime_reports/dm_console_combat_service_read_model_composition_smoke_evidence_20260708.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_smoke_evidence_20260707.md`
- `logs/smoke/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture_smoke-server_20260708-122320.log`
- `logs/debug-trace-20260708-122320.jsonl`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `dnd_initative_tracker.py`
- `server_runtime.py`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_planning_checkpoint_20260708.md`
- `docs/runtime_reports/dm_console_combat_route_request_overlap_planning_20260708.md`

## Analysis and Decisions

1. **Refinement 82b996a Kept**: The service and internal read-model composition spans (`combat_service.combat_snapshot` p95: `384.238 ms` and `dm.console.combat_snapshot.service_call` p95: `386.362 ms`) show a material improvement (~23% reduction).
2. **Interpretation of HTTP Regression**: The `/api/dm/combat` p95 regression (`936.898 ms` -> `1352.821 ms`) is driven by a single slow request outlier over a long 2+ hour run with only 19 total requests, which is not statistically significant to prove a systemic bottleneck.
3. **No Direct Route Implementation**: The current evidence is not detailed enough to distinguish JSON response serialization overhead, threadpool queue scheduling delays, or event-loop overlap.
4. **Recommended Next Step**: Recommend `WORK-20260708-dm-console-combat-route-request-overlap-instrumentation` as targeted instrumentation / evidence to trace response serialization and threadpool queue delays.
5. **Deferred Scope**: Resource-pools remains closed; startup static fields and the small smoke bug remain separately deferred.

## Validation

All required validation commands ran successfully:
- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-122320.jsonl`
- `timeout 10s git diff --check`
- `git status --short`

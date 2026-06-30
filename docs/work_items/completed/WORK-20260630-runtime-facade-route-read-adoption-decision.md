# WORK-20260630-runtime-facade-route-read-adoption-decision: Runtime facade route-read adoption decision

## Status

Completed.

## Type

Bounded planning/decision pass.

## Goal

Create the durable decision for whether and how existing HTTP read/snapshot route paths should adopt `ServerRuntimeFacade.read_snapshot()`.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `server_runtime.py` (inspected targeted range around `read_snapshot`)
- `dnd_initative_tracker.py` (inspected targeted range around `_current_request_wants_tactical_map` and `_dm_console_snapshot`)

## Files Created / Modified

- Created: `docs/planning/living_docs/server_runtime_route_read_adoption_decision_20260630.md`
- Created and then deleted: `docs/work_items/active/WORK-20260630-runtime-facade-route-read-adoption-decision.md`
- Created: `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-decision.md`
- Modified: `docs/work_items/current_work.md`

## Decisions Reached

1. **Adoption Candidate Selected:** The pure read endpoint `GET /api/dm/combat` is selected as the safest first endpoint for route-read adoption. It has no side effects or mutations. Queue-backed mutation endpoints that return snapshots are also prime candidates for subsequent steps.
2. **Exclusion of High-Risk Routes:** Gameplay mutation routes (like rules-aware move, AoE create) remain deferred since their command/write paths are not yet migrated to the facade.
3. **Adoption Strategy:** The route will invoke `read_snapshot(snapshot_type="dm_console")` with explicit `include_tactical` derived from the existing request path context. On failure, the route layer will fail closed, mapping errors to HTTP 500/503. Payload compatibility is strictly preserved.
4. **Evidence Needs:** Adopting the minimal read boundary is ready now. No separate timing/telemetry evidence pass is needed.
5. **Next Task:** Recommended exact next task is `WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation`.

## Validation

- Py compile and check command outputs verified.
- Pre-existing untracked files are untouched.

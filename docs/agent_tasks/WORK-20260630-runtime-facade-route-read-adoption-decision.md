# WORK-20260630-runtime-facade-route-read-adoption-decision

## Executor

AGY / Antigravity CLI

## Mode

Bounded planning/decision pass only.

## Goal

Create the durable decision for whether and how existing HTTP read/snapshot route paths should adopt `ServerRuntimeFacade.read_snapshot()`.

This task did not implement route adoption. It selected the narrowest safe first adoption slice.

## Source documents

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `server_runtime.py`
- `tests/test_server_runtime.py`
- `dnd_initative_tracker.py`
- `combat_service.py`

## Files changed

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_route_read_adoption_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-decision.md`

## Targeted source ranges inspected

- `server_runtime.py` lines 820-865: `_resolve_dm_console_include_tactical(...)`
- `server_runtime.py` lines 870-1020: `ServerRuntimeFacade.read_snapshot()`
- `dnd_initative_tracker.py` lines 170-186: `_current_request_wants_tactical_map()`
- `dnd_initative_tracker.py` around line 2512: `self._runtime` assignment
- `dnd_initative_tracker.py` lines 3160-3180: FastAPI middleware and route handler `submit_command(...)` interaction
- `dnd_initative_tracker.py` lines 8406-8515: `_dm_console_snapshot(...)` and `_dm_console_snapshot_payload(...)`

## Decision

The safest first route-read adoption candidate is:

- `GET /api/dm/combat`

Reason:

- It is a pure read endpoint.
- It minimizes regression risk compared with mutation routes.
- It can adopt the new read façade without reopening direct gameplay route migration.
- Existing response dictionary structure must be preserved.

## Adoption strategy selected

The later implementation slice should route `GET /api/dm/combat` through `ServerRuntimeFacade.read_snapshot()` using `dm_console` mode.

The implementation must:

- Pass explicit `include_tactical` based on `_current_request_wants_tactical_map()`.
- Preserve existing response payload compatibility.
- Fail closed at the route layer by mapping façade errors/exceptions to the current appropriate HTTP failure behavior.
- Avoid direct gameplay route migration.
- Avoid route offload and instrumentation.
- Avoid any queue, WebSocket, gameplay, LAN, Tk, cache, or deployment changes.

## Explicitly deferred

- rules-aware move
- AoE create
- structures
- ships
- boarding links
- route offload
- instrumentation
- gameplay mutation changes
- broad direct-route migration

## Selected next task

`WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation`

Reason:

`ServerRuntimeFacade.read_snapshot()` already exists and has focused contract coverage. The decision found the first safe adoption target is ready without a separate evidence-capture pass.

## Validation

- `git status --short`
- `timeout 10s git diff --check`

Validation passed with no `git diff --check` output. Pre-existing untracked `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/` remained untouched.

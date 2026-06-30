# WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation

Status: Completed

## Goal

Adopt the first selected HTTP read route, `GET /api/dm/combat`, to use `ServerRuntimeFacade.read_snapshot()` through the new read/snapshot runtime boundary.

This was a narrow route-read adoption slice only.

## Source documents

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_route_read_adoption_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-decision.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`

## Files changed

- `dnd_initative_tracker.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`

## Implementation summary

`GET /api/dm/combat` now calls `ServerRuntimeFacade.read_snapshot()` with a `RuntimeSnapshotRequest` using `snapshot_type="dm_console"`.

The route passes explicit request context through `params={"include_tactical": _current_request_wants_tactical_map()}`.

Successful responses return `result.data`, preserving the existing response payload shape.

Failure behavior remains fail-closed:

- `runtime_not_ready` maps to HTTP 503.
- Other unsuccessful snapshot results map to HTTP 500.
- Unexpected exceptions map to the existing generic HTTP 500 route behavior.

## Scope exclusions

This task did not change:

- `server_runtime.py`
- `init_tracker_server/app.py`
- `init_tracker_server/runtime.py`
- `server_app.py`
- `combat_service.py`
- `_dm_console_snapshot()`
- `_dm_console_snapshot_payload()`
- cache ownership
- cache TTLs
- cache invalidation
- queue behavior
- WebSocket behavior
- gameplay mutation behavior
- LAN controller behavior
- Tk behavior
- deployment topology
- browser/UI behavior

No direct gameplay route migration was performed.

## Test posture

The existing focused runtime test suite was run. A broad route integration test was not added in this slice because the available quick route harness would require duplicating the route handler rather than exercising the production route. Production behavior should be verified by a bounded developer smoke/evidence pass.

## Validation

Required validation:

- `git status --short`
- `timeout 10s git diff --check`
- `timeout 10s .venv/bin/python -m py_compile dnd_initative_tracker.py tests/test_server_runtime.py`
- `timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q`

## Next safe action

Run a bounded developer smoke/evidence pass for `GET /api/dm/combat` route-read adoption before selecting another read route or any mutation-route work.

Do not jump to player-command routes or high-risk direct gameplay route migration from this work item.

## Developer smoke evidence

Smoke command:

- `INIT_TRACKER_DEBUGGING=1 .venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787`

Smoke log:

- `logs/smoke/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation_smoke-server_20260630-164720.log`

Debug trace:

- `logs/debug-trace-20260630-164720.jsonl`

Result:

- Headless server started without startup crash or traceback.
- DM operator surface and player LAN surface were advertised.
- LAN sessions connected and disconnected normally.
- A player session claimed Fred successfully.
- Developer ran a small combat test and reported the page worked normally.
- Developer observed the webpage remained responsive while processing was happening, which is useful evidence that server-first ownership is improving perceived responsiveness.
- Debug trace included `GET /api/dm/combat` with `workspace` query, HTTP 200, and successful snapshot spans.
- Trace also showed known follow-up latency evidence: `_dm_console_snapshot` around 94 ms, the HTTP request around 113 ms, and later standalone `_lan_snapshot` slow spans around 385–390 ms.

Smoke decision:

- This route-read adoption slice is smoke-passed.
- The slow `_lan_snapshot` spans should be preserved as follow-up evidence for the snapshot/read-model lane.
- Do not treat this smoke as authorization to jump into player-command routes, direct gameplay route migration, rules-aware move, AoE create, structures, ships, or boarding links.

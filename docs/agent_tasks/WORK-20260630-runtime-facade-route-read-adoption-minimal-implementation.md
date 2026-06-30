# WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation

## Executor

AGY / Antigravity CLI

## Mode

Bounded implementation pass.

## Goal

Implement the first route-read adoption slice selected by the route-read adoption decision: route `GET /api/dm/combat` through `ServerRuntimeFacade.read_snapshot()` using `dm_console` mode, while preserving existing response payload compatibility.

## Source documents

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_route_read_adoption_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-decision.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`

## Allowed files

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`

## Final accepted source change

`GET /api/dm/combat` now constructs a `RuntimeSnapshotRequest` with `snapshot_type="dm_console"` and explicit `include_tactical` params resolved from `_current_request_wants_tactical_map()`.

The accepted route change preserves response payload compatibility and maps failed snapshot results to HTTP errors.

## Cleanup note

The initial agent pass attempted two out-of-scope changes:

- adding `self._runtime.start()` in `LanController.start()`
- adding a fake copied FastAPI route test that did not exercise the production route

Both were removed before commit.

## Forbidden scope preserved

No direct route migration, mutation-route migration, route offload, instrumentation, queue/WebSocket/gameplay/Tk/LAN behavior change, cache relocation, cache TTL change, deployment, browser smoke, Codex, or Gemini.

## Validation

- `git status --short`
- `timeout 10s git diff --check`
- `timeout 10s .venv/bin/python -m py_compile dnd_initative_tracker.py tests/test_server_runtime.py`
- `timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q`

## Next safe action

Bounded developer smoke/evidence pass for `GET /api/dm/combat` route-read adoption.

# WORK-20260630-runtime-facade-runtime-reexport-boundary: Runtime facade re-export boundary

## Status

Completed.

## Type

Focused implementation slice.

## Goal

Add `init_tracker_server/runtime.py` as a stable package runtime import/re-export boundary while preserving `server_runtime.py` as the implementation source and preserving existing command, route, queue, trace, and test behavior.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Initial `HEAD` evidence:

```text
007c710
```

The current-work ledger was `Idle` at the start of this pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-import-boundary-plan.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`
- `server_app.py`
- `server_runtime.py`
- `tests/test_server_health.py`
- `tests/test_server_runtime.py`
- `tests/test_server_app.py`
- `tests/test_headless_host.py`

## Files Changed

- `init_tracker_server/runtime.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`

## Package Files Created Or Changed

- Created `init_tracker_server/runtime.py`.
- Left `init_tracker_server/__init__.py` unchanged.
- Left `init_tracker_server/app.py` unchanged.

## Re-export Boundary

`init_tracker_server.runtime` now imports from and re-exports the current public runtime boundary from `server_runtime.py`:

- `ServerRuntimeFacade`
- `RuntimeCommand`
- `RuntimeCommandResult`
- `RuntimeCommandTrace`
- `RuntimeSnapshotRequest`
- `RuntimeSnapshotResult`
- `STATUS_ACCEPTED`
- `STATUS_QUEUED`
- `STATUS_DISPATCHING`
- `STATUS_COMPLETED`
- `STATUS_FAILED`
- `STATUS_TIMED_OUT`
- `COMMAND_UPDATE_SPELL_COLOR`
- `COMMAND_TEST_QUEUE`
- `COMMAND_SET_FACING`
- `COMMAND_SET_AURAS_ENABLED`
- `COMMAND_PLACE_COMBATANT`
- `COMMAND_REMOVE_AOE`
- `COMMAND_MOVE_AOE`
- `COMMAND_SET_OBSTACLE`
- `COMMAND_SET_TERRAIN`
- `COMMAND_SET_ELEVATION`
- `COMMAND_SET_MAP_SETTINGS`
- `COMMAND_UPSERT_MAP_BACKGROUND`
- `COMMAND_REMOVE_MAP_BACKGROUND`
- `COMMAND_SET_MAP_BACKGROUND_ORDER`
- `COMMAND_UPSERT_MAP_HAZARD`
- `COMMAND_REMOVE_MAP_HAZARD`
- `COMMAND_UPSERT_MAP_FEATURE`
- `COMMAND_REMOVE_MAP_FEATURE`

## Compatibility Preserved

`server_runtime.py` remains the implementation source and was not edited.

Existing direct imports from `server_runtime.py` remain valid. `server_app.py`, `init_tracker_server/app.py`, route behavior, queue submission and polling, timeout/error mapping, trace status/metadata behavior, WebSocket behavior, snapshot/cache behavior, gameplay/combat/map mutation behavior, deployment topology, and process startup behavior were not changed.

## Tests Added Or Updated

`tests/test_server_runtime.py` now includes `test_package_runtime_reexports_current_runtime_boundary`, which proves:

- `init_tracker_server.runtime` imports successfully.
- `init_tracker_server.runtime.ServerRuntimeFacade is server_runtime.ServerRuntimeFacade`.
- key command constants, status constants, command contracts, snapshot contracts, and trace contracts are available from `init_tracker_server.runtime` and match `server_runtime.py`.

No route behavior tests were changed.

## Validation

Required validation was run after the implementation and ledger updates:

- `python3 -m py_compile init_tracker_server/runtime.py init_tracker_server/__init__.py tests/test_server_runtime.py tests/test_server_health.py tests/test_server_app.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py tests/test_server_health.py tests/test_server_app.py`
- `timeout 10s git diff --check`
- `git status --short`

Full command output is recorded in the final report for this pass.

## Remaining Inline / Out Of Scope

All runtime implementation remains in `server_runtime.py`.

No branches or commands were migrated, no handlers or dispatchers were introduced, and no runtime logic was moved. `_lan_apply_action()` remains unchanged.

## Risks / Rough Edges

This is an import-boundary-only slice. The app factory still imports `ServerRuntimeFacade` directly from `server_runtime.py`; changing package-internal imports to use `init_tracker_server.runtime` should be a separate compatibility-preserving slice if desired.

## Next Broad Pass

The best next broad pass is a package-internal import realignment decision: decide whether `init_tracker_server/app.py` should import `ServerRuntimeFacade` through `init_tracker_server.runtime` now, or whether the repo should defer that until a broader runtime/commands module split is authorized.


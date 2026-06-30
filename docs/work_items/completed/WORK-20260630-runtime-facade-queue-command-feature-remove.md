# WORK-20260630-runtime-facade-queue-command-feature-remove: Queue-backed facade command for map feature removal

## Status

Completed.

## Type

Bounded implementation slice.

## Strategic Lane

ASGI server first, runtime as a service.

## Goal

Route only `DELETE /api/dm/map/features/{feature_id}` through `ServerRuntimeFacade.submit_command(...)` and the existing Tk/LanController queue adapter seam, preserving existing map feature removal behavior.

## Scope

- Added `COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"` constant to `server_runtime.py`.
- Routed `COMMAND_REMOVE_MAP_FEATURE` in `ServerRuntimeFacade.submit_command` via the queue adapter seam.
- Added dispatch logic for `typ == "remove_map_feature"` in `_lan_apply_action` in `dnd_initative_tracker.py` on the Tk/main thread.
- Updated `DELETE /api/dm/map/features/{feature_id}` in `dnd_initative_tracker.py` to delegate to the facade.
- Added focused unit tests in `tests/test_server_runtime.py` for map feature removal command execution, validation errors, and route mapping.

## Non-Goals / Forbidden Scope

- Did not migrate map structures.
- Did not migrate `POST /api/dm/map/aoes`.
- Did not migrate `POST /api/dm/map/combatants/{cid}/move`.
- Did not bundle feature removal with any other endpoint.
- Did not change `POST /api/dm/map/features` except for shared constants/imports already established by the feature-upsert slice.
- Did not change movement, pathfinding, turn state, hazards-trigger gameplay behavior, riders/mounts, prompts, reactions, opportunity behavior, HP, spells, combat state, AoE lifecycle, structures/collision behavior, deployment config, or unrelated routes.
- Did not touch `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`.
- Did not edit `logs/context/`.
- Did not inspect old plans, `majorTODO.md`, historical runtime reports, archived docs, broad logs, or unrelated test files.
- Did not run full test suites.
- Did not push, deploy, restart services, SSH elsewhere, or alter production topology.
- Did not create a checkpoint doc.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-next-queue-command-selection-12.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-command-feature-upsert.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-command-hazard-remove.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/active/WORK-20260630-runtime-facade-queue-command-feature-remove.md`

## Files Edited

- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-command-feature-remove.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-queue-command-feature-remove.md`

## Validation

Required bounded validation passed:
- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py`
- `timeout 10s git diff --check`
- `git status --short`

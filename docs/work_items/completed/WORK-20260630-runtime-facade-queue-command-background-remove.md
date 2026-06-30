# WORK-20260630-runtime-facade-queue-command-background-remove: Queue-backed facade command for map background removal

## Status

Completed.

## Type

Bounded implementation slice.

## Strategic Lane

ASGI server first, runtime as a service.

## Goal

Route only `DELETE /api/dm/map/backgrounds/{bid}` through `ServerRuntimeFacade.submit_command(...)` and the existing Tk/LanController queue adapter seam, preserving existing map background removal behavior.

## Scope

- Added `COMMAND_REMOVE_MAP_BACKGROUND = "remove_map_background"` constant to `server_runtime.py`.
- Routed `COMMAND_REMOVE_MAP_BACKGROUND` in `ServerRuntimeFacade.submit_command` via the queue adapter seam.
- Added dispatch logic for `typ == "remove_map_background"` in `_lan_apply_action` in `dnd_initative_tracker.py` on the Tk/main thread.
- Updated `DELETE /api/dm/map/backgrounds/{bid}` in `dnd_initative_tracker.py` to delegate to the facade.
- Added focused unit tests in `tests/test_server_runtime.py` for map background removal command execution, validation errors, and route mapping.

## Non-Goals / Forbidden Scope

- Did not migrate POST /api/dm/map/backgrounds/{bid}/order.
- Did not migrate POST /api/dm/map/aoes.
- Did not migrate POST /api/dm/map/combatants/{cid}/move.
- Did not bundle background removal and background ordering.
- Did not change movement, pathfinding, turn state, hazards, riders/mounts, prompts, reactions, opportunity behavior, HP, spells, combat state, AoE lifecycle, deployment config, or unrelated routes.
- Did not touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md.
- Did not triage unrelated bugs.
- Did not inspect old plans, majorTODO.md, historical runtime reports, archived docs, broad logs, or unrelated test files.
- Did not run full test suites.
- Did not push, deploy, restart services, SSH elsewhere, or alter production topology.

## Files Inspected

- docs/work_items/current_work.md
- docs/work_items/completed/WORK-20260630-runtime-facade-next-queue-command-selection-10.md
- docs/work_items/completed/WORK-20260630-runtime-facade-queue-command-backgrounds.md
- docs/work_items/completed/WORK-20260630-runtime-facade-next-queue-command-selection-9.md
- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py

## Files Edited

- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py
- docs/work_items/current_work.md
- docs/work_items/active/WORK-20260630-runtime-facade-queue-command-background-remove.md

## Validation

All validation checks passed successfully:
- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py` (42/42 tests passed)

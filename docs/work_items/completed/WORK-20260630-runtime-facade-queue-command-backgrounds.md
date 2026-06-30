# WORK-20260630-runtime-facade-queue-command-backgrounds: Queue-backed facade command for map backgrounds

## Status

Completed.

## Type

Bounded implementation slice.

## Strategic Lane

ASGI server first, runtime as a service.

## Goal

Route only POST /api/dm/map/backgrounds through ServerRuntimeFacade.submit_command(...) and the existing Tk/LanController queue adapter seam, preserving existing map background upsert behavior and focused test coverage.

## Scope

- Added `COMMAND_UPSERT_MAP_BACKGROUND = "upsert_map_background"` constant to `server_runtime.py`.
- Routed `COMMAND_UPSERT_MAP_BACKGROUND` in `ServerRuntimeFacade.submit_command` via the queue adapter seam.
- Added dispatch logic for `typ == "upsert_map_background"` in `_lan_apply_action` in `dnd_initative_tracker.py` on the Tk/main thread.
- Updated `POST /api/dm/map/backgrounds` in `dnd_initative_tracker.py` to delegate to the facade.
- Added focused unit tests in `tests/test_server_runtime.py` for map background command execution, validation errors, and route mapping.

## Non-Goals

- Did not migrate POST /api/dm/map/aoes.
- Did not migrate POST /api/dm/map/combatants/{cid}/move.
- Did not change movement, pathfinding, turn state, hazards, riders/mounts, prompts, reactions, opportunity behavior, HP, spells, combat state, AoE lifecycle, deployment config, or unrelated routes.
- Did not touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md.
- Did not triage unrelated bugs.
- Did not inspect old plans, majorTODO.md, historical runtime reports, archived docs, broad logs, or unrelated test files.
- Did not run full test suites.
- Did not push, deploy, restart services, SSH elsewhere, or alter production topology.

## Files Inspected

- docs/work_items/current_work.md
- docs/work_items/completed/WORK-20260630-runtime-facade-next-queue-command-selection-9.md
- docs/work_items/completed/WORK-20260630-runtime-facade-queue-command-map-settings.md
- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py

## Files Edited

- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py
- docs/work_items/current_work.md

## Validation

All validation checks passed successfully:
- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py` (39/39 tests passed)

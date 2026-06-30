# WORK-20260629-runtime-facade-queue-command-obstacle-cell: Queue-backed facade command for obstacle cell toggle

## Status

Completed.

## Type

Bounded implementation slice.

## Strategic Lane

ASGI server first, runtime as a service.

## Goal

Migrate only POST /api/dm/map/obstacles/cell through ServerRuntimeFacade.submit_command(...) and the facade queue adapter seam, preserving existing behavior and focused test coverage.

## Source Decision

Recommended by docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection-5.md.

## Scope

- Added `COMMAND_SET_OBSTACLE = "set_obstacle"` to [server_runtime.py](../../../server_runtime.py).
- Routed `COMMAND_SET_OBSTACLE` in `ServerRuntimeFacade.submit_command` via the queue adapter seam.
- Added dispatch logic for `typ == "set_obstacle"` in `_lan_apply_action` in [dnd_initative_tracker.py](../../../dnd_initative_tracker.py) on the Tk/main thread.
- Updated `POST /api/dm/map/obstacles/cell` in [dnd_initative_tracker.py](../../../dnd_initative_tracker.py) to delegate to the facade.
- Added focused unit tests in [tests/test_server_runtime.py](../../../tests/test_server_runtime.py) for obstacle cell toggle command execution, error mapping, and route mapping.

## Non-Goals

- Did not migrate terrain cell.
- Did not migrate combatant move.
- Did not migrate AoE routes, combatant facing, aura overlays, turn, HP, spellcasting, broad combat, initiative, save/load, deploy, smoke, or unrelated bug paths.
- Did not alter gameplay semantics, map rendering, obstacle behavior, queue timeout policy, or production topology.

## Files Inspected

- docs/work_items/current_work.md
- docs/work_items/active/WORK-20260629-runtime-facade-queue-command-obstacle-cell.md
- docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection-5.md
- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py

## Files Edited

- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py
- docs/work_items/active/WORK-20260629-runtime-facade-queue-command-obstacle-cell.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-obstacle-cell.md
- docs/work_items/current_work.md

## Validation

All validation checks passed successfully:
- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py` (27/27 tests passed)
- `timeout 10s git diff --check`

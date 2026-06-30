# WORK-20260630-runtime-facade-queue-command-terrain-cell: Queue-backed facade command for terrain cell toggle

## Status

Completed.

## Type

Bounded implementation slice.

## Strategic Lane

ASGI server first, runtime as a service.

## Goal

Route only POST /api/dm/map/terrain/cell through ServerRuntimeFacade.submit_command(...) and the facade queue adapter seam, preserving existing behavior and focused test coverage.

## Source Decision

Recommended by [WORK-20260630-runtime-facade-next-queue-command-selection-6](WORK-20260630-runtime-facade-next-queue-command-selection-6.md).

## Scope

- Added `COMMAND_SET_TERRAIN = "set_terrain"` to [server_runtime.py](../../../server_runtime.py).
- Routed `COMMAND_SET_TERRAIN` in `ServerRuntimeFacade.submit_command` via the queue adapter seam.
- Added dispatch logic for `typ == "set_terrain"` in `_lan_apply_action` in [dnd_initative_tracker.py](../../../dnd_initative_tracker.py) on the Tk/main thread.
- Updated `POST /api/dm/map/terrain/cell` in [dnd_initative_tracker.py](../../../dnd_initative_tracker.py) to delegate to the facade.
- Added focused unit tests in [tests/test_server_runtime.py](../../../tests/test_server_runtime.py) for terrain cell toggle command execution, error mapping, and route mapping.

## Non-Goals

- Did not migrate combatant move.
- Did not migrate AoE routes, combatant facing, aura overlays, turn, HP, spellcasting, broad combat, initiative, save/load, deploy, smoke, or unrelated bug paths.
- Did not alter gameplay semantics, map rendering, terrain cell logic, queue timeout policy, or production topology.

## Files Inspected

- docs/work_items/current_work.md
- docs/work_items/completed/WORK-20260630-runtime-facade-next-queue-command-selection-6.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-obstacle-cell.md
- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py

## Files Edited

- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py
- docs/work_items/completed/WORK-20260630-runtime-facade-queue-command-terrain-cell.md
- docs/work_items/current_work.md

## Validation

All validation checks passed successfully:
- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py` (30/30 tests passed)

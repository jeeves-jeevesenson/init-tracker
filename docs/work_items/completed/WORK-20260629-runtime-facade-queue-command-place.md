# WORK-20260629-runtime-facade-queue-command-place

## Status

Completed

## Completion Evidence

Completed by AGY implementation pass `AGY-20260629-runtime-facade-queue-command-place`.

### Implementation Summary

- Added `COMMAND_PLACE_COMBATANT = "place_combatant"` in `server_runtime.py`.
- Routed `COMMAND_PLACE_COMBATANT` through `ServerRuntimeFacade.submit_command(...)` and the queue adapter seam.
- Registered `"place_combatant"` in `LanController._ACTION_MESSAGE_TYPES`.
- Added the `"place_combatant"` queue action branch in `_lan_apply_action` to invoke `_dm_place_combatant_on_map` synchronously on the Tk thread.
- Mapped validation error results to `ValueError` (HTTP 400) and runtime exception errors to `RuntimeError` (HTTP 500) to match existing error behavior.
- Added focused tests in `tests/test_server_runtime.py` covering success, validation failure, exception mapping, trace state, and route-level behavior.

### Validation

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py` -> Passed.
- `.venv/bin/python -m unittest tests/test_server_runtime.py` -> Passed (18 tests OK).
- `git diff --check` -> Passed.


## Goal

Migrate only `POST /api/dm/map/combatants/{cid}/place` through `ServerRuntimeFacade.submit_command(...)` and the facade queue adapter seam.

Preserve existing route behavior, payload shape, admin token handling, response shape, and Tk/LanController authority.

## Strategic lane

ASGI server first, runtime as a service.

## Source planning

This implementation slice follows:

- `docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection-2.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-auras.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-facing.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md`

## Required behavior

- Add a bounded facade command constant for placing/repositioning a combatant.
- Route only `POST /api/dm/map/combatants/{cid}/place` through `ServerRuntimeFacade.submit_command(...)`.
- Add only the minimal LanController/Tk queue action handling needed for this route if no existing action mapping exists.
- Preserve existing direct behavior and response semantics.
- Preserve existing `set_facing`, `set_auras_enabled`, spell-color, and unknown-command behavior.
- Preserve queue-backed command tracing for completed, failed, and timed-out paths.

## Likely files

- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

## Forbidden scope

Do not migrate `move`.

Do not migrate AoE movement.

Do not change broad combat, turn, HP, spellcasting, AoE, movement-budget, hazard, mount/rider, or state-transition behavior.

Do not triage unrelated bug inbox dirt.

Do not touch `logs/context`.

Do not deploy, push, restart services, or alter production topology.

## Validation

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py`
- `timeout 10s git diff --check`

## Completion criteria

- The place/reposition route is queue-backed through the facade.
- Existing behavior is preserved.
- Focused tests cover the new command path.
- Ledger is returned to Idle and this document is moved to `docs/work_items/completed/`.

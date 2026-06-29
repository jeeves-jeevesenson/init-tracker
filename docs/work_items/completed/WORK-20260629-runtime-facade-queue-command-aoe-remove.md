# WORK-20260629-runtime-facade-queue-command-aoe-remove

## Status

Completed

## Completion Evidence

Completed by AGY implementation pass `AGY-20260629-runtime-facade-queue-command-aoe-remove`.

### Implementation Summary

- Added `COMMAND_REMOVE_AOE = "aoe_remove"` in `server_runtime.py`.
- Routed `COMMAND_REMOVE_AOE` through `ServerRuntimeFacade.submit_command(...)` and the queue adapter seam.
- Registered `"aoe_remove"` in `LanController._ACTION_MESSAGE_TYPES` (pre-existing).
- Intercepted `"aoe_remove"` for admin in `_lan_apply_action` to run `_dm_remove_aoe_on_map` synchronously on the Tk thread and record the result on the action state.
- Routed the `DELETE /api/dm/map/aoes/{aid}` route handler through the facade runtime queue seam.
- Mapped validation error results to `ValueError` (HTTP 400) to match existing error behavior.
- Added focused tests in `tests/test_server_runtime.py` covering success, validation failure, trace state, and route-level behavior.

### Validation

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py` -> Passed.
- `.venv/bin/python -m unittest tests/test_server_runtime.py` -> Passed (21 tests OK).
- `git diff --check` -> Passed.

## Goal

Migrate only `DELETE /api/dm/map/aoes/{aid}` through `ServerRuntimeFacade.submit_command(...)` and the facade queue adapter seam.

Preserve existing route behavior, payload shape, response shape, error behavior, and Tk/LanController authority.

## Strategic lane

ASGI server first, runtime as a service.

## Source planning

This implementation slice follows:

- `docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection-3.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-place.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-auras.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-facing.md`
- `docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md`

## Required behavior

- Add a bounded facade command constant for AoE removal.
- Route only `DELETE /api/dm/map/aoes/{aid}` through `ServerRuntimeFacade.submit_command(...)`.
- Reuse the existing `aoe_remove` LanController/Tk queue action mapping if supported by current code.
- Preserve existing direct route response and error semantics.
- Preserve existing spell-color, set-facing, set-auras-enabled, place-combatant, and unknown-command behavior.
- Preserve queue-backed command tracing for completed, failed, and timed-out paths.

## Likely files

- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

## Forbidden scope

Do not migrate AoE move.

Do not migrate combatant move.

Do not change broad combat, turn, HP, spellcasting, AoE geometry, movement-budget, hazard, mount/rider, or state-transition behavior.

Do not edit `player_command_contracts.py` or `player_command_service.py`.

Do not triage unrelated bug inbox dirt.

Do not touch `logs/context`.

Do not deploy, push, restart services, or alter production topology.

## Validation

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py`
- `timeout 10s git diff --check`

## Completion criteria

- The AoE remove route is queue-backed through the facade.
- Existing behavior is preserved.
- Focused tests cover the new command path.
- Ledger is returned to Idle and this document is moved to `docs/work_items/completed/`.

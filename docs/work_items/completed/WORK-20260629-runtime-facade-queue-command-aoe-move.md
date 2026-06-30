# WORK-20260629-runtime-facade-queue-command-aoe-move: Queue-backed facade command for AoE move

## Status

Completed.

## Type

Bounded implementation slice.

## Strategic Lane

ASGI server first, runtime as a service.

## Goal

Migrate only POST /api/dm/map/aoes/{aid}/move through ServerRuntimeFacade.submit_command(...) and the facade queue adapter seam, preserving existing behavior and focused test coverage.

## Source Decision

Recommended by docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection-4.md.

## Scope

This slice may add a facade command constant for AoE move if one does not already exist.

This slice may route only POST /api/dm/map/aoes/{aid}/move through ServerRuntimeFacade.submit_command(...).

This slice may add or adjust focused tests in tests/test_server_runtime.py for the AoE move route and command trace behavior.

## Non-Goals

Do not migrate combatant move.

Do not migrate AoE create, AoE remove, AoE listing, combatant placement, facing, aura overlays, turn, HP, spellcasting, broad combat, initiative, save/load, deploy, smoke, or unrelated bug paths.

Do not alter gameplay semantics, AoE geometry, targeting behavior, map rendering, queue timeout policy, or production topology.

Do not triage inbox bugs or clean logs/context.

## Files to Inspect First

- docs/work_items/current_work.md
- docs/work_items/active/WORK-20260629-runtime-facade-queue-command-aoe-move.md
- docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection-4.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-aoe-remove.md
- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py

## Allowed Files for Implementation

- server_runtime.py
- dnd_initative_tracker.py
- tests/test_server_runtime.py
- docs/work_items/active/WORK-20260629-runtime-facade-queue-command-aoe-move.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-aoe-move.md
- docs/work_items/current_work.md

## Required Implementation Shape

- Add or reuse one command constant for AoE move.
- Route only POST /api/dm/map/aoes/{aid}/move through ServerRuntimeFacade.submit_command(...).
- Reuse existing LanController/Tk queue action support where available.
- Preserve current response payloads and error behavior.
- Preserve existing RuntimeCommandTrace behavior for completed, failed, and timed-out queue-backed command paths.
- Add or update focused tests only for this route and trace path.

## Validation

Run these bounded validation commands:

- python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
- .venv/bin/python -m unittest tests/test_server_runtime.py
- timeout 10s git diff --check

## Completion Criteria

This work item is complete when only POST /api/dm/map/aoes/{aid}/move is queue-backed through the facade adapter, focused validation passes, and current_work.md is returned to Idle with this work item recorded in Recently Completed.

## Implementation Evidence

- Defined `COMMAND_MOVE_AOE = "aoe_move"` in `server_runtime.py`.
- Routed `COMMAND_MOVE_AOE` through `ServerRuntimeFacade.submit_command(...)`.
- Intercepted `"aoe_move"` in `InitiativeTracker._lan_apply_action` to execute `_dm_move_aoe_on_map` on the Tk thread and record the result under `move_result`.
- Updated `POST /api/dm/map/aoes/{aid}/move` in `dnd_initative_tracker.py` to route through the facade runtime queue seam and map response/errors appropriately.
- Added focused tests in `tests/test_server_runtime.py` covering success, validation failure, trace state, and route-level behavior.

## Validation Results

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py` -> Passed.
- `.venv/bin/python -m unittest tests/test_server_runtime.py` -> Passed (24 tests OK).
- `timeout 10s git diff --check` -> Passed.

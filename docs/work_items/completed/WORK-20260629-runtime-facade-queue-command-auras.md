# WORK-20260629-runtime-facade-queue-command-auras

## Status

Completed

## Title

Queue-backed facade command for map aura overlays

## Goal

Migrate `POST /api/dm/map/overlays/auras` to execute through `ServerRuntimeFacade.submit_command(...)` using the existing queue adapter seam.

This is the next production queue-backed facade command migration after combatant facing. It must preserve existing endpoint behavior while routing the mutation through the facade-owned command boundary and existing command/action authority path.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:

- docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-facing.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-selection.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md
- docs/work_items/completed/WORK-20260628-command-queue-semantics.md
- docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md

## Required Implementation Shape

Implement a narrow production command boundary for aura overlay toggling.

The implementation should:

1. Add or reuse an explicit runtime command constant for `set_auras_enabled`.
2. Route only `POST /api/dm/map/overlays/auras` through `ServerRuntimeFacade.submit_command(...)`.
3. Have the facade adapt that command onto the existing queue adapter seam.
4. Preserve the existing command/action dictionary shape for `set_auras_enabled`.
5. Preserve existing endpoint response semantics as closely as current behavior allows.
6. Preserve authority boundaries; do not bypass the selected queue/action path from the FastAPI route.
7. Preserve existing spell-color and set-facing command behavior.
8. Preserve unknown command fail-closed behavior.
9. Record command trace status and queue metadata for the aura overlay command path.

## Non-Goals

Do not:
- migrate any route except `POST /api/dm/map/overlays/auras`,
- change movement, token placement, turn advancement, combat resolution, AoE, spellcasting, HP, conditions, tactical movement, or other gameplay rules,
- edit unrelated routes,
- alter LanController queue mechanics,
- change WebSocket message semantics,
- implement snapshot cache or read-boundary changes,
- triage unrelated bugs,
- touch logs/context/,
- touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md,
- revive old plans, majorTODO.md, runtime reports, or completed work,
- run browser smoke,
- deploy,
- push.

## Files To Inspect First

1. docs/work_items/current_work.md
2. docs/work_items/active/WORK-20260629-runtime-facade-queue-command-auras.md
3. docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection.md
4. docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-facing.md
5. server_runtime.py
6. tests/test_server_runtime.py
7. dnd_initative_tracker.py targeted sections only for:
   - `POST /api/dm/map/overlays/auras`
   - `set_auras_enabled`
   - `LanController._actions`
   - `LanController._tick`
   - queue/status result handling
8. player_command_contracts.py targeted sections only for `set_auras_enabled` command constants/categories
9. player_command_service.py targeted sections only for `set_auras_enabled` handling

## Allowed Files To Edit

- server_runtime.py
- tests/test_server_runtime.py
- dnd_initative_tracker.py

## Validation

Validation commands for this implementation slice:

    python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
    .venv/bin/python -m unittest tests/test_server_runtime.py
    git status --short
    timeout 10s git diff --check

## Close Criteria

This work item can close when:

1. `POST /api/dm/map/overlays/auras` routes through `ServerRuntimeFacade.submit_command(...)`.
2. The facade submits the aura overlay command through the queue adapter seam.
3. Existing command/action authority remains the execution path.
4. Existing spell-color and set-facing behavior remains covered.
5. Unknown command behavior remains fail-closed.
6. Focused tests cover the new command mapping and trace behavior.
7. No unrelated route or gameplay behavior changes are made.
8. All scoped validation commands pass.
9. The ledger is updated to mark this item completed or move to the next active work item.


---

## Completion Evidence

Completed by AGY implementation pass `AGY-20260629-runtime-facade-queue-command-auras`.

### Implementation Summary

- Added `COMMAND_SET_AURAS_ENABLED = "set_auras_enabled"` in `server_runtime.py`.
- Routed `COMMAND_SET_AURAS_ENABLED` through `ServerRuntimeFacade.submit_command(...)` and the existing queue adapter seam.
- Migrated only `POST /api/dm/map/overlays/auras` in `dnd_initative_tracker.py`.
- Preserved the existing `set_auras_enabled` command/action payload shape using `enabled` and `admin_token`.
- Preserved existing spell-color and set-facing command behavior.
- Preserved unknown command fail-closed behavior.
- No other route was migrated.

### Test Coverage Summary

Focused tests in `tests/test_server_runtime.py` cover:

- `COMMAND_SET_AURAS_ENABLED` queue adapter success.
- queued action dictionary payload containing the expected aura overlay fields.
- completed command trace metadata for the aura overlay path.
- route-level response mapping for success, invalid payload, timeout, ValueError, and generic runtime failure behavior.
- existing spell-color and set-facing behavior.
- unknown command fail-closed behavior.

### Validation

AGY reported these validations passed:

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py`
  - `Ran 15 tests in 0.439s`
  - `OK`
- `timeout 10s git diff --check`
  - clean output

### Scope Confirmation

- Changed files: `server_runtime.py`, `tests/test_server_runtime.py`, `dnd_initative_tracker.py`.
- Exact route migrated: `POST /api/dm/map/overlays/auras`.
- No movement, token placement, facing, turn advancement, combat resolution, AoE, spellcasting, HP, conditions, tactical movement, or other gameplay rules changed.
- No player command contract or player command service files edited.
- No browser smoke, deploy, or push performed.

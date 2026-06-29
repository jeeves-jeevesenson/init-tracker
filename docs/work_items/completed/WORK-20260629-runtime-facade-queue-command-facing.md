# WORK-20260629-runtime-facade-queue-command-facing

## Status

Completed

## Title

Queue-backed facade command for combatant facing

## Goal

Migrate `POST /api/dm/map/combatants/{cid}/facing` to execute through `ServerRuntimeFacade` using the new queue adapter seam.

This is the first production queue-backed facade command migration. It must preserve existing endpoint behavior while routing the mutation through the facade-owned command boundary and existing `LanController._actions` / Tk-thread authority path.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:

- docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-selection.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter-evidence.md
- docs/work_items/completed/WORK-20260628-command-queue-semantics.md
- docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md

## Required Implementation Shape

Implement a narrow production command boundary for combatant facing.

The implementation should:

1. Add an explicit runtime command constant for the facing update.
2. Route only `POST /api/dm/map/combatants/{cid}/facing` through `ServerRuntimeFacade.submit_command(...)`.
3. Have the facade adapt that command onto the existing queue adapter seam.
4. Preserve the existing LAN/Tk action dictionary shape for `set_facing`.
5. Preserve existing endpoint response semantics as closely as current behavior allows.
6. Preserve Tk thread authority; do not call `_lan_apply_action` directly from FastAPI request handling.
7. Preserve existing spell-color command behavior.
8. Preserve unknown command fail-closed behavior.
9. Record command trace status and queue metadata for the facing command path.

## Non-Goals

Do not:
- migrate any route except `POST /api/dm/map/combatants/{cid}/facing`,
- change movement, turn advancement, combat resolution, AoE, spellcasting, or tactical rules,
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
2. docs/work_items/active/WORK-20260629-runtime-facade-queue-command-facing.md
3. docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-selection.md
4. docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md
5. server_runtime.py
6. tests/test_server_runtime.py
7. dnd_initative_tracker.py targeted sections only for:
   - `POST /api/dm/map/combatants/{cid}/facing`
   - `set_facing`
   - `LanController._actions`
   - `LanController._tick`
   - `LanController._lan_apply_action`
   - queue/status result handling

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

1. `POST /api/dm/map/combatants/{cid}/facing` routes through `ServerRuntimeFacade.submit_command(...)`.
2. The facade submits the facing command through the queue adapter seam.
3. Existing `set_facing` LAN/Tk authority remains the execution path.
4. Existing spell-color behavior remains covered.
5. Unknown command behavior remains fail-closed.
6. Focused tests cover the new command mapping and trace behavior.
7. No unrelated route or gameplay behavior changes are made.
8. All scoped validation commands pass.
9. The ledger is updated to mark this item completed or move to the next active work item.


---

## Completion Evidence

Completed by AGY implementation pass `AGY-20260629-runtime-facade-queue-command-facing`.

### Implementation Summary

- Added `COMMAND_SET_FACING = "set_facing"` in `server_runtime.py`.
- Routed `COMMAND_SET_FACING` through `ServerRuntimeFacade.submit_command(...)` and the existing queue adapter seam.
- Migrated only `POST /api/dm/map/combatants/{cid}/facing` in `dnd_initative_tracker.py`.
- Preserved Tk thread authority by submitting through the existing `LanController._actions` queue path.
- Preserved local combatant existence validation to keep expected HTTP 400 behavior.
- Preserved existing spell-color command behavior.
- Preserved unknown command fail-closed behavior.
- No other route was migrated.

### Test Coverage Summary

Focused tests in `tests/test_server_runtime.py` cover:

- `COMMAND_SET_FACING` queue adapter success.
- queued action dictionary payload containing `type`, `cid`, and `facing_deg`.
- completed command trace metadata for the facing path.
- existing `COMMAND_UPDATE_SPELL_COLOR` behavior.
- unknown command fail-closed behavior.

### Validation

AGY reported these validations passed:

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py`
  - `Ran 13 tests in 0.434s`
  - `OK`
- `timeout 10s git diff --check`
  - clean output

### Scope Confirmation

- Changed files: `server_runtime.py`, `tests/test_server_runtime.py`, `dnd_initative_tracker.py`.
- Exact route migrated: `POST /api/dm/map/combatants/{cid}/facing`.
- No movement, turn advancement, combat resolution, AoE, spellcasting, HP, conditions, tactical movement, or other gameplay rules changed.
- No LanController queue mechanics changed.
- No browser smoke, deploy, or push performed.

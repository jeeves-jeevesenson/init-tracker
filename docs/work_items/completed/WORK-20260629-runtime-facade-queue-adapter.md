# WORK-20260629-runtime-facade-queue-adapter

## Status

Completed

## Title

Runtime facade queue adapter seam

## Goal

Implement the facade-side queue adapter seam inside ServerRuntimeFacade so future mutating and gameplay commands can be submitted through the existing LanController._actions queue while keeping gameplay authority on the Tk GUI thread.

This is an implementation slice for the adapter seam only. It must not migrate production FastAPI routes or alter LanController gameplay behavior.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:

- docs/work_items/completed/WORK-20260628-runtime-facade-skeleton.md
- docs/work_items/completed/WORK-20260628-runtime-facade-contracts.md
- docs/work_items/completed/WORK-20260628-command-queue-semantics.md
- docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md
- docs/work_items/completed/WORK-20260629-runtime-facade-next-boundary-evidence.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter-evidence.md

## Required Implementation Shape

Implement a narrow facade-side helper such as ServerRuntimeFacade._submit_to_lan_queue(command).

The adapter should:

1. Map a RuntimeCommand payload into the dictionary shape expected by the existing LanController._actions / _lan_apply_action flow.
2. Register pending action state under lan_controller._action_states_lock.
3. Enqueue onto lan_controller._actions.
4. Wait on the request thread by polling action state until completion or timeout.
5. Preserve Tk thread authority by allowing LanController._tick to drain and execute the action.
6. Return RuntimeCommandResult on success.
7. Record RuntimeCommandTrace for completed, failed, and timed out outcomes.
8. Use a bounded timeout, with 5000 ms as the initial target unless implementation evidence requires a different explicit constant.
9. Keep the existing synchronous COMMAND_UPDATE_SPELL_COLOR behavior unchanged unless tests prove a tiny refactor is needed for shared trace handling.

## Non-Goals

Do not:
- migrate any FastAPI route,
- edit dnd_initative_tracker.py,
- edit server_app.py,
- implement snapshot cache or read-boundary changes,
- alter gameplay, combat, tactical, LAN, Tk, or WebSocket behavior,
- change production WebSocket message semantics,
- triage unrelated bugs,
- touch logs/context/,
- touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md,
- revive old plans, majorTODO.md, runtime reports, or completed work,
- run browser smoke,
- deploy,
- push.

## Files To Inspect First

1. docs/work_items/current_work.md
2. docs/work_items/active/WORK-20260629-runtime-facade-queue-adapter.md
3. docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter-evidence.md
4. docs/work_items/completed/WORK-20260628-command-queue-semantics.md
5. docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md
6. server_runtime.py
7. tests/test_server_runtime.py
8. dnd_initative_tracker.py targeted sections only for LanController._actions, _action_states, _action_states_lock, _tick, _lan_apply_action, queue_size, queue_wait_ms

## Allowed Files To Edit

- server_runtime.py
- tests/test_server_runtime.py

## Validation

Validation commands for this implementation slice:

    python3 -m py_compile server_runtime.py tests/test_server_runtime.py
    .venv/bin/python -m unittest tests/test_server_runtime.py
    git status --short
    timeout 10s git diff --check

## Close Criteria

This work item can close when:

1. ServerRuntimeFacade has a narrow queue adapter seam for future queue-backed commands.
2. Existing COMMAND_UPDATE_SPELL_COLOR behavior remains covered and unchanged.
3. Focused tests cover queue success, queue timeout, queue failure or error-result mapping, and trace metadata.
4. No production route is migrated.
5. No LanController or gameplay behavior is changed.
6. All scoped validation commands pass.
7. The ledger is updated to mark this item completed or move to the next active work item.


---

## Completion Evidence

Completed by AGY implementation pass `AGY-20260629-runtime-facade-queue-adapter`.

### Implementation Summary

- Added `ServerRuntimeFacade._submit_to_lan_queue(command, timeout_ms=5000)` in `server_runtime.py`.
- The helper converts a `RuntimeCommand` into the existing `LanController._actions` dictionary flow.
- It registers pending action state under `lan_controller._action_states_lock`.
- It enqueues the action onto `lan_controller._actions`.
- It polls bounded action state from the request thread until completion or timeout.
- It preserves Tk authority by not calling `_lan_apply_action` directly.
- It records `RuntimeCommandTrace` for completed, failed, and timed-out outcomes.
- Existing `COMMAND_UPDATE_SPELL_COLOR` direct behavior remains covered and unchanged.
- Unknown commands remain fail-closed.
- Only a test seam command was routed through the new adapter; no production FastAPI route was migrated.

### Test Coverage Summary

Focused tests in `tests/test_server_runtime.py` cover:

- existing spell-color command success and completed trace behavior,
- queue adapter success,
- queue adapter timeout with a fast test timeout,
- queue adapter mapped error/failure behavior,
- unknown command fail-closed behavior.

### Validation

AGY reported these validations passed:

- `python3 -m py_compile server_runtime.py tests/test_server_runtime.py`
- `.venv/bin/python -m unittest tests/test_server_runtime.py`
  - `Ran 12 tests in 0.424s`
  - `OK`
- `timeout 10s git diff --check`
  - clean output

### Scope Confirmation

- Changed files: `server_runtime.py`, `tests/test_server_runtime.py`.
- No production routes migrated.
- No `dnd_initative_tracker.py` edits.
- No `server_app.py` edits.
- No gameplay, combat, tactical, LAN, Tk, or WebSocket behavior changed.

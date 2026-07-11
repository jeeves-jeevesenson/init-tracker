# WORK-20260710-combat-mutation-event-loop-containment-decision

Status: Completed

## Goal

Select the smallest safe combat-mutation family and exact existing authoritative queue seam for containing the synchronous ASGI event-loop blocking confirmed by the controlled-repeat evidence, without implementing the decision.

## Files Inspected

- `docs/agent_tasks/templates/task-packet.md`
- `docs/work_items/current_work.md`
- `docs/architecture/Init-Tracker-Updated-Migration-Assessment-2026-07-09.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md`
- `docs/runtime_reports/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `combat_service.py`
- `tests/test_server_runtime.py`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260710-combat-mutation-event-loop-containment-decision.md`
- `docs/planning/living_docs/combat_mutation_event_loop_containment_decision_20260710.md`
- `docs/runtime_reports/combat_mutation_event_loop_containment_decision_20260710.md`

## Decision

Selected **Outcome A - implementation-ready**.

The smallest coherent family is all three evidence-proven DM lifecycle/turn routes:

- `POST /api/dm/combat/start`
- `POST /api/dm/combat/set-turn`
- `POST /api/dm/combat/next-turn`

All three perform DM authentication and service availability checks, delegate to one `CombatService` instance, synchronously mutate tracker turn state, call `_lan_force_state_broadcast()`, and return a DM snapshot. Splitting the family would duplicate the same queue, authority, result, snapshot, trace, and rollback plumbing while leaving a proven sibling route on the event loop.

The exact next item is:

- **ID:** `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`
- **Type:** Narrow implementation
- **Permitted implementation files:** `server_runtime.py`, `dnd_initative_tracker.py`, and `tests/test_server_runtime.py`
- **Read-only/reused service:** `combat_service.py`

## Required Implementation Shape

- Add `COMMAND_COMBAT_START = "combat_start"`, `COMMAND_COMBAT_SET_TURN = "combat_set_turn"`, and `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"` in `server_runtime.py`.
- Reuse `RuntimeCommand`, `ServerRuntimeFacade.submit_command()`, `ServerRuntimeFacade._submit_to_lan_queue()`, `LanController._actions`, `LanController._tick()`, `InitiativeTracker._lan_apply_action()`, and `LanController._action_states`.
- Execute unchanged `CombatService.start_combat()`, `CombatService.set_turn_here(cid)`, and `CombatService.next_turn()` from `_lan_apply_action()` on the Tk/headless-root authority thread.
- Store the raw service result under `combat_result` and the exact route response snapshot under `response_snapshot` in the action state before `_tick()` marks the command completed.
- Build `response_snapshot` on the authority thread, using the current route-specific snapshot behavior and an explicit `include_tactical` value captured by the route. Do not rebuild it synchronously after the await on the ASGI loop.
- Run `ServerRuntimeFacade.submit_command()` and its 5 ms bounded `_action_states` polling loop inside `starlette.concurrency.run_in_threadpool()`. Keep the existing `5000 ms` timeout.
- Preserve the HTTP request trace ID through worker, facade, queue, dispatch, service, broadcast, and response spans while retaining a distinct queue action ID and parent request action ID.
- Preserve the current direct route adapters behind one temporary pre-request queue/direct rollback switch. Never automatically retry the direct path after enqueue or timeout because the authoritative command may still complete.

## Compatibility

Existing route success, validation, auth, service-unavailable, domain-failure, unexpected-failure, and response payload behavior must remain byte/schema compatible. A queue wait timeout is the only new transport outcome and maps to HTTP 504, matching existing queue-backed facade routes.

The selected methods currently make no separate persistence API call; the implementation must neither add nor remove persistence behavior. Player claims do not authorize these routes. Route `_check_dm_auth()` remains authoritative, and the queued message must carry an internally validated/issued admin token so `_lan_apply_action()` does not broaden player claim permissions.

## Validation

- No application tests were run for this planning-only task.
- `timeout 10s git diff --check`: required after documentation updates.
- `git status --short`: required for the final report.

No application code, tests, routes, queue behavior, commit, push, deploy, restart, browser smoke, or production action was changed or run.

# Combat Mutation Event-Loop Containment Decision

Date: 2026-07-10

Work item: `WORK-20260710-combat-mutation-event-loop-containment-decision`

Status: Completed; Outcome A; ledger paused

## Selected Family

The first implementation must migrate exactly these routes as one coherent family:

- `POST /api/dm/combat/start`
- `POST /api/dm/combat/set-turn`
- `POST /api/dm/combat/next-turn`

The family is coherent because each route is a DM-authenticated synchronous adapter over `CombatService`, each changes lifecycle or active-turn state, each force-broadcasts the resulting tracker state, and each returns a DM console snapshot. The controlled trace reproduced stalls around every member. No HP, movement, monster capability, resource, previous-turn, combat-end, long-rest, route-registration, WebSocket-ownership, or public command-lifecycle work belongs in this slice.

## Exact Command Contract

| Route | Command | Service method | Domain payload | Facade result |
| --- | --- | --- | --- | --- |
| `POST /api/dm/combat/start` | `COMMAND_COMBAT_START = "combat_start"` | `CombatService.start_combat()` | none | `combat_result`, `response_snapshot` |
| `POST /api/dm/combat/set-turn` | `COMMAND_COMBAT_SET_TURN = "combat_set_turn"` | `CombatService.set_turn_here(cid)` | `cid` | `combat_result`, `response_snapshot` |
| `POST /api/dm/combat/next-turn` | `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"` | `CombatService.next_turn()` | none | `combat_result`, `response_snapshot` |

Every internal command payload also carries `admin_token`, `include_tactical`, `timeout_ms=5000`, `request_trace_id`, and `parent_action_id`. These are internal transport/correlation fields and do not alter the HTTP schema.

The facade must return the unchanged raw service dictionary as `combat_result`. Domain `ok: false` is not converted into a generic facade error; the route retains its existing status/detail mapping. Missing queue result or response snapshot is a transport/runtime failure.

## Authority And Threading

The required path is:

`async FastAPI route -> run_in_threadpool(worker) -> ServerRuntimeFacade.submit_command() -> _submit_to_lan_queue() -> LanController._actions -> Tk/headless-root _tick() -> InitiativeTracker._lan_apply_action() -> CombatService method -> force broadcast + response snapshot -> _action_states completion -> worker return -> async route response`

Thread ownership is explicit:

- The ASGI loop performs auth, request validation, worker scheduling, result-to-HTTP mapping, and response return only.
- A Starlette worker executes `submit_command()` and its current 5 ms polling wait. `time.sleep()` must never run on the ASGI loop.
- Tk/headless-root `_tick()` remains the sole mutation authority and calls `_lan_apply_action()`.
- `CombatService` retains its existing `RLock` and delegates to the existing tracker methods on the authority thread.
- LAN snapshot construction, DM broadcast snapshot construction, and the route's final response snapshot are completed before the action state is marked complete.
- `run_coroutine_threadsafe()` schedules LAN and DM fanout coroutines onto the ASGI loop; it does not transfer tracker authority.

## Compatibility Requirements

| Route | Preserved successful response | Preserved failures |
| --- | --- | --- |
| start | HTTP 200, `{ok: true, snapshot}` | auth 401; service unavailable 503; no combatants/service rejection 400; unexpected failure 500 with current detail |
| set-turn | HTTP 200, `{ok: true, cid, previous_cid, snapshot}` | auth 401; service unavailable 503; invalid payload/missing or non-integer cid 400; no active combat/not found 400; unexpected failure 500 with current detail |
| next-turn | HTTP 200, `{ok: true, snapshot}` | auth 401; service unavailable 503; service `ok: false` 500; invalid combat snapshot 500; unexpected failure 500 with current detail |

Queue timeout maps to HTTP 504 using the existing queue-backed route convention. No success or domain outcome changes status. Response top-level keys and snapshot visibility/tactical behavior remain unchanged.

Route `_check_dm_auth()` must run before worker dispatch. The route then follows the existing queue-backed DM pattern of forwarding a valid bearer token or issuing an internal admin token after successful auth. This authorizes an admin command inside `_lan_apply_action()` without introducing player claim semantics. No automatic direct fallback is allowed after enqueue or timeout.

The selected service methods currently do not call a separate persistence API. Existing in-memory turn state, logs/history, refresh, snapshot, and broadcast side effects remain unchanged; no persistence behavior is added.

## Broadcast Boundary

After migration, `_lan_force_state_broadcast()` still runs synchronously on the authority thread. It builds the LAN snapshot, cached state, DM broadcast snapshot, and schedules LAN/DM fanout.

Fanout can still consume ASGI-loop time because `_broadcast_state_async()` builds dynamic/personalized payloads and JSON on the loop, while `_push_dm_snapshot_async()` JSON-serializes and sends the DM snapshot on the loop. The controlled evidence showed broadcast construction, rather than the small DM send span, as the dominant selected-write cost. This residual fanout risk is bounded by required spans and the developer smoke gate; it does not require a WebSocket ownership redesign in this implementation.

## Required Trace Contract

- `dm.combat.command.threadpool_dispatch_queue`: route schedules worker to worker entry.
- `dm.combat.command.worker_wait`: worker entry through facade return/exception.
- `runtime.command.queue_wait`: facade enqueue to `_tick()` authority dispatch start.
- `runtime.command.execute`: full authority-thread `_lan_apply_action()` command execution.
- `combat.mutation.service_call`: exact `CombatService` method duration and outcome.
- `combat.mutation.response_snapshot`: final route snapshot construction on the authority thread.
- Existing `_lan_force_state_broadcast`, `lan.snapshot.build`, and `dm.console.snapshot.build`: broadcast construction.
- `lan.broadcast.schedule` and `dm.broadcast.schedule`: authority-thread `run_coroutine_threadsafe()` scheduling only.
- Existing `lan.broadcast.state` and `dm.broadcast.snapshot`: event-loop serialization/fanout.
- `dm.combat.command.worker_return`: action completion observed through worker exit.
- `dm.combat.command.route_resume`: worker completion to coroutine resumption.
- Existing `http.request`: total HTTP duration.

Every span/event must carry the same HTTP `trace_id`, the queue `action_id`, `parent_action_id`, command, route, method, outcome, and `thread_role` (`asgi`, `worker`, or `authority`) where applicable. Queue spans also carry queue size and enqueue-to-start duration. Broadcast spans carry recipient count, serialized bytes, build duration, schedule duration, and fanout duration.

## Rollback Boundary

Keep the current three direct route adapters intact as private route-local helpers during the first implementation. A single temporary internal switch, `INIT_TRACKER_COMBAT_MUTATION_QUEUE=queue|direct`, is evaluated before command submission and defaults to `queue` for the implementation evidence run. `direct` invokes the preserved current adapter before any enqueue occurs.

Rollback must be selected before request handling. A timed-out or failed queued command is never retried directly because it may already be executing or may complete later. The switch does not alter HTTP schemas and is removed only in a later explicitly authorized cleanup after accepted smoke evidence.

## Exact Next Item

- **ID:** `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`
- **Type:** Implementation
- **Files:** `server_runtime.py`, `dnd_initative_tracker.py`, `tests/test_server_runtime.py`
- **Reused unchanged:** `combat_service.py`

No additional instrumentation-only task is required. The exact trace additions are part of the narrow implementation and its acceptance gate.

See the [completed decision](../../work_items/completed/WORK-20260710-combat-mutation-event-loop-containment-decision.md) and [runtime report](../../runtime_reports/combat_mutation_event_loop_containment_decision_20260710.md).

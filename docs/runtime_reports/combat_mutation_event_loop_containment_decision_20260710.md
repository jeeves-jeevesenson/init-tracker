# Combat Mutation Event-Loop Containment Decision

Date: 2026-07-10

Work item: `WORK-20260710-combat-mutation-event-loop-containment-decision`

## Outcome

**Outcome A - implementation-ready.**

Recommend `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`, type implementation, limited to the three selected routes and `server_runtime.py`, `dnd_initative_tracker.py`, and `tests/test_server_runtime.py`. `combat_service.py` is reused unchanged.

## Current Route Mapping

| Method and route | Direct route behavior | Service/authority behavior | Current response and errors |
| --- | --- | --- | --- |
| `POST /api/dm/combat/start` | `_check_dm_auth`; require `_dm_service`; call `_dm_service.start_combat()`; call `_dm_console_snapshot()` | `CombatService.start_combat()` locks, requires combatants, calls tracker `_start_turns()`, sets `in_combat`, force-broadcasts, returns combat snapshot | 200 `{ok, snapshot}`; auth 401; unavailable 503; service rejection 400; unexpected 500 `Failed to start combat.` |
| `POST /api/dm/combat/set-turn` | `_check_dm_auth`; require service; validate object payload and integer `cid`; call `_dm_service.set_turn_here(cid)`; call `_dm_console_snapshot()` | Service locks, requires active combat and existing cid, changes `current_cid`, normalizes `turn_num`, runs start-of-turn effects, logs/rebuilds, force-broadcasts, returns cid/previous cid/combat snapshot | 200 `{ok, cid, previous_cid, snapshot}`; auth 401; unavailable 503; payload/domain rejection 400; unexpected 500 `Failed to set turn.` |
| `POST /api/dm/combat/next-turn` | `_check_dm_auth`; require service; call `_dm_service.next_turn()`; validate returned combat snapshot; call `_dm_console_snapshot(combat_snapshot=...)` | Service locks, calls tracker `_next_turn()` with turn cleanup/effects/history, rebuilds, force-broadcasts, returns combat snapshot | 200 `{ok, snapshot}`; auth 401; unavailable 503; service/invalid snapshot 500; unexpected 500 `Failed to advance turn.` |

All route and service work is currently invoked by the async handler on the Uvicorn/ASGI loop. The service's `RLock` serializes service access but does not move execution to the tracker authority thread. `_lan_force_state_broadcast()` synchronously builds LAN and DM snapshot payloads before scheduling fanout coroutines. The route then performs its final `_dm_console_snapshot()` synchronously.

The selected methods contain no explicit session/YAML persistence call. Migration must preserve that behavior exactly. Authentication is DM admin authentication, not a player claim decision.

## Existing Queue And Facade Seams

`RuntimeCommand` contains `command_type` and a dictionary `payload`. `ServerRuntimeFacade.submit_command()` selects a command branch. `_submit_to_lan_queue()`:

1. creates a queue action ID, trace ID, and received timestamp;
2. builds the legacy message shape;
3. registers pending state under `_action_states_lock`;
4. puts the message on `LanController._actions`;
5. polls `_action_states` every `5 ms` for up to `5000 ms`;
6. maps queue error reasons to exceptions;
7. returns `RuntimeCommandResult` and queue metadata or raises `TimeoutError`.

`LanController._tick()` explicitly runs on the Tk/headless-root thread. It dequeues `_actions`, computes queue wait, sets debug correlation, calls `InitiativeTracker._lan_apply_action(msg)`, records completion/error in `_action_states`, and emits dispatch traces. Existing focused tests prove success, timeout, mapped errors, queue message shape, result extraction, route-level mapping, and trace metadata for queue-backed commands.

The synchronous facade polling loop is safe only in a worker thread. Calling `submit_command()` directly from an async route would reproduce event-loop blocking even though mutation authority moved to the queue.

## Decision Questions

1. **Are the three routes coherent?** Yes. They are one DM lifecycle/turn family with the same auth, service, force-broadcast, snapshot, queue, and rollback shape. A narrower split would duplicate plumbing and leave a proven sibling direct.
2. **Which routes migrate first?** Exactly `POST /api/dm/combat/start`, `POST /api/dm/combat/set-turn`, and `POST /api/dm/combat/next-turn` together.
3. **Which command/service names?** `COMMAND_COMBAT_START = "combat_start"` -> `CombatService.start_combat()`; `COMMAND_COMBAT_SET_TURN = "combat_set_turn"` -> `CombatService.set_turn_here(cid)`; `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"` -> `CombatService.next_turn()`.
4. **Which queue seams?** `RuntimeCommand`, `ServerRuntimeFacade.submit_command()`, `_submit_to_lan_queue()`, `LanController._actions`, Tk-thread `_tick()`, `InitiativeTracker._lan_apply_action()`, and `_action_states` completion/result storage.
5. **Where does the wait run?** In a Starlette worker entered with `run_in_threadpool()`. The ASGI handler awaits that worker and never runs `_submit_to_lan_queue()` or its `time.sleep()` polling directly.
6. **Can HTTP contracts remain unchanged?** Yes for every existing outcome: 200, 400, 401, 500, and 503 mappings and exact response keys/details remain. Queue timeout alone maps to the existing facade convention of 504.
7. **What stays on the authority thread?** Tracker mutation, `CombatService` execution, table/log/turn side effects, `_lan_force_state_broadcast()`, LAN/DM snapshot construction, final route response snapshot construction, and action-state result completion.
8. **Can fanout still block the event loop?** Yes. `run_coroutine_threadsafe()` schedules work, but LAN dynamic/personalized payload serialization and DM JSON serialization/send still execute in their ASGI-loop coroutines. Required schedule/fanout spans and smoke thresholds bound this residual risk without broadening to WebSocket ownership.
9. **Which spans are required?** `dm.combat.command.threadpool_dispatch_queue`, `dm.combat.command.worker_wait`, `runtime.command.queue_wait`, `runtime.command.execute`, `combat.mutation.service_call`, `combat.mutation.response_snapshot`, existing broadcast-build spans, `lan.broadcast.schedule`, `dm.broadcast.schedule`, existing fanout spans, `dm.combat.command.worker_return`, `dm.combat.command.route_resume`, and total `http.request`, all correlated by request trace, queue action, and parent action IDs.
10. **Which tests and smoke are required?** The focused unit/route/thread/trace tests and controlled developer smoke gate below.
11. **What is the rollback boundary?** Preserve the current direct route adapters behind `INIT_TRACKER_COMBAT_MUTATION_QUEUE=queue|direct`, chosen before enqueue. Never retry direct after a queued failure/timeout.
12. **Is implementation sufficiently specified?** Yes. Instrumentation is narrow and ships with the implementation; no additional evidence-only item is required first.

## Required Future Tests

Add focused tests named for these behaviors:

- `test_combat_start_command_queue_success`
- `test_combat_set_turn_command_queue_success`
- `test_combat_next_turn_command_queue_success`
- `test_combat_mutation_command_runs_on_tick_authority`
- `test_combat_mutation_response_snapshot_precedes_action_completion`
- `test_combat_mutation_routes_offload_queue_wait`
- `test_combat_mutation_route_contract_mapping`
- `test_combat_mutation_queue_timeout_mapping`
- `test_combat_mutation_trace_correlation`
- `test_combat_mutation_direct_rollback_selected_before_enqueue`

Coverage must prove raw service result preservation, route-specific domain mapping, exact response keys, auth before dispatch, no player-claim broadening, a single service invocation and force broadcast, no route-side synchronous snapshot build, 5-second timeout behavior, no automatic retry, and request/queue/broadcast trace correlation.

Future implementation validation is limited to:

```bash
python3 -m py_compile server_runtime.py dnd_initative_tracker.py
timeout 120s .venv/bin/python -m unittest \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_start_command_queue_success \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_set_turn_command_queue_success \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_next_turn_command_queue_success \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_command_runs_on_tick_authority \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_response_snapshot_precedes_action_completion \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_routes_offload_queue_wait \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_route_contract_mapping \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_queue_timeout_mapping \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_trace_correlation \
  tests.test_server_runtime.ServerRuntimeFacadeTests.test_combat_mutation_direct_rollback_selected_before_enqueue
```

No whole-suite run is required by the future implementation unless a focused failure requires a separately named bounded diagnostic.

## Developer Smoke Gate

After focused tests pass, a developer-run controlled smoke must use the established `212`-combatant (`10` player / `202` monster) shape, connected LAN and DM WebSocket clients, at least `30` tactical combat GETs, one combat start, at least five set-turn requests, and at least five next-turn requests within a dense five-minute window.

Acceptance requires:

- exact 200 response keys and state transitions for all three routes;
- configured-auth 401 and service/domain error mappings remain unchanged in targeted probes;
- no queue timeout or duplicate mutation;
- one correlated trace chain per mutation through worker, queue, authority, service, broadcast build, response snapshot, fanout schedule, worker return, and HTTP completion;
- no selected-write post-worker/route-resume gap of `250 ms` or more;
- health/readiness p95 below `50 ms` during the bounded mixed load;
- fanout schedule and serialization durations reported separately, with any event-loop fanout span at or above `250 ms` treated as a blocker requiring a new narrow evidence decision;
- direct rollback mode exercised separately before enqueue and shown to preserve the current response contract.

Browser smoke, production deployment, restart, commit, and push remain developer-owned and are not part of this planning task.

## Exact Next Action

- **ID:** `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`
- **Type:** Narrow implementation
- **Files:** `server_runtime.py`, `dnd_initative_tracker.py`, `tests/test_server_runtime.py`
- **Ledger:** paused until explicitly opened

See the [completed work item](../work_items/completed/WORK-20260710-combat-mutation-event-loop-containment-decision.md) and [living planning record](../planning/living_docs/combat_mutation_event_loop_containment_decision_20260710.md).

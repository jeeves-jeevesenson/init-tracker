# Combat Mutation Event-Loop Containment Minimal Implementation

Date: 2026-07-11

Work item: `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`

Status: Implemented and focused-validation passed; active pending developer smoke evidence

## Implemented Boundary

Exactly these routes moved to the existing authoritative queue in the default mode:

- `POST /api/dm/combat/start` -> `COMMAND_COMBAT_START = "combat_start"`
- `POST /api/dm/combat/set-turn` -> `COMMAND_COMBAT_SET_TURN = "combat_set_turn"`
- `POST /api/dm/combat/next-turn` -> `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"`

No other combat, HP, movement, monster, map, rest, previous-turn, or combat-end route moved.

## Runtime Shape

The implemented queue path is:

`async route -> run_in_threadpool(worker) -> ServerRuntimeFacade.submit_command() -> _submit_to_lan_queue() -> LanController._actions -> Tk/headless-root _tick() -> InitiativeTracker._lan_apply_action() -> unchanged CombatService method -> force broadcast -> final response snapshot -> _action_states completion -> worker return -> async route response`

Auth and public request validation remain before worker dispatch. The worker owns the complete synchronous facade submission and its 5 ms bounded polling wait. The authority branch calls only `CombatService.start_combat()`, `CombatService.set_turn_here(cid)`, or `CombatService.next_turn()` for the selected mutation. It then builds the route's final DM snapshot and stores both `combat_result` and `response_snapshot` before returning to `_tick()`, which marks the action completed.

Every command carries `admin_token`, `include_tactical`, `timeout_ms=5000`, `request_trace_id`, and `parent_action_id`; set-turn also carries `cid`. The facade preserves the raw service dictionary and does not normalize domain errors.

## Rollback Boundary

`INIT_TRACKER_COMBAT_MUTATION_QUEUE=queue|direct` is evaluated before enqueue for each selected request. Missing and invalid values resolve to the documented `queue` default. Exact `direct` calls the three preserved private route-local direct adapters. Once queue mode submits a command, timeout or failure is returned through the queue error path and is never retried directly.

## Compatibility

The queue adapters retain the existing successful response keys and fixed error-detail strings. Start and set-turn retain their 400 domain mappings. Next-turn retains its 500 service-false and invalid-service-snapshot mappings. Auth remains 401, service unavailable remains 503, existing unexpected paths remain 500, and queue timeout alone adds 504.

No public request schema changed. No player claim authority was introduced. The route forwards a valid bearer token or issues the existing internal admin token after successful DM auth.

## Trace Contract

Added:

- `dm.combat.command.threadpool_dispatch_queue`
- `dm.combat.command.worker_wait`
- `runtime.command.queue_wait`
- `runtime.command.execute`
- `combat.mutation.service_call`
- `combat.mutation.response_snapshot`
- `lan.broadcast.schedule`
- `dm.broadcast.schedule`
- `dm.combat.command.worker_return`
- `dm.combat.command.route_resume`

The new spans carry the HTTP trace ID, queue or parent action correlation as available, command, route, method, outcome, and `thread_role`. Queue instrumentation records queue size, timeout, completion state, and enqueue-to-authority-start duration. Schedule spans measure only authority-thread scheduling and recipient counts. Existing `lan.broadcast.state` and `dm.broadcast.snapshot` continue to own serialized-byte and asynchronous fanout evidence; no WebSocket ownership redesign was attempted.

## Focused Validation

- Python compilation passed.
- The first focused pytest run exposed only a new fixture error involving the read-only `LanController.app` property; 93 tests passed and 5 fixture/trace-cascade failures occurred.
- The single permitted focused rerun passed all 95 tests in 1.28 seconds after correcting the fixture to use tracker-backed app ownership.
- Final whitespace/status evidence is recorded in the runtime report and final task report.

## Remaining Decision

Do not close or move this work item yet. Developer acceptance still requires the established 212-combatant controlled smoke with tactical reads, repeated start/set-turn/next-turn mutations, response verification, duplicate/timeout checks, correlated traces, and health/readiness/fanout thresholds from the active work item.

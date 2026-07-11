# Combat Mutation Event-Loop Containment Minimal Implementation

**ID:** `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`
**Status:** Active
**Type:** Implementation
**Opened:** 2026-07-11

## Goal

Move exactly these DM combat mutation routes through the existing authoritative runtime queue:

- `POST /api/dm/combat/start`
- `POST /api/dm/combat/set-turn`
- `POST /api/dm/combat/next-turn`

Preserve synchronous HTTP compatibility while ensuring the facade's bounded polling wait runs in a Starlette worker rather than on the ASGI event loop.

## Source Decision

- `docs/planning/living_docs/combat_mutation_event_loop_containment_decision_20260710.md`
- `docs/runtime_reports/combat_mutation_event_loop_containment_decision_20260710.md`
- `docs/work_items/completed/WORK-20260710-combat-mutation-event-loop-containment-decision.md`

## Exact Command Family

- `COMMAND_COMBAT_START = "combat_start"`
- `COMMAND_COMBAT_SET_TURN = "combat_set_turn"`
- `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"`

Required authority path:

`async route -> run_in_threadpool -> ServerRuntimeFacade.submit_command() -> _submit_to_lan_queue() -> LanController._actions -> _tick() -> _lan_apply_action() -> unchanged CombatService method -> broadcast and response snapshot -> action completion -> worker return -> route response`

## Allowed Files

Only:

- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/active/WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation.md`
- `docs/planning/living_docs/combat_mutation_event_loop_containment_minimal_implementation_20260711.md`
- `docs/runtime_reports/combat_mutation_event_loop_containment_minimal_implementation_20260711.md`

`combat_service.py` is read-only.

## Required Behavior

- Preserve authentication before worker dispatch.
- Preserve successful HTTP 200 response keys.
- Preserve current 400, 401, 500, and 503 behavior.
- Map queue timeout only to HTTP 504.
- Preserve snapshot visibility and tactical behavior.
- Execute mutation, force-broadcast construction, and final response snapshot on the Tk/headless-root authority thread.
- Never retry a timed-out or failed queued command through the direct path.
- Add `INIT_TRACKER_COMBAT_MUTATION_QUEUE=queue|direct`.
- Default the switch to `queue`.
- Select the rollback path before enqueue.

## Required Instrumentation

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

Preserve existing HTTP and broadcast spans.

Correlation must retain the HTTP trace ID and include action ID, parent action ID, command, route, outcome, and thread role where applicable.

## Forbidden Scope

Do not change:

- HP, movement, previous-turn, combat-end, long-rest, monster capability, or resource routes
- route-registration ownership
- public asynchronous command semantics
- WebSocket ownership or protocols
- persistence
- cache or resource-pools behavior
- startup static-fields behavior
- Uvicorn or ASGI configuration
- gameplay, visibility, claims, authentication, reconnect, or production topology

Do not touch:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`

## Focused Validation

Run only:

    .venv/bin/python -m py_compile server_runtime.py dnd_initative_tracker.py
    timeout 120s .venv/bin/python -m pytest tests/test_server_runtime.py
    timeout 10s git diff --check
    git status --short

No full repository test suite is authorized.

## Acceptance Gate

Unit tests alone do not accept the implementation.

The later developer smoke must use:

- the established 212-combatant shape;
- at least 30 tactical combat GETs;
- combat start and repeated set-turn/next-turn mutations;
- unchanged route responses;
- no duplicate commands or timeouts;
- health/readiness p95 below 50 ms;
- no selected-write route-resume or fanout span at or above 250 ms.

## Completion

Stop after focused validation and reporting.

Codex must not commit, push, deploy, restart services, run browser smoke, SSH elsewhere, or alter production.

## Implementation Summary

Implemented on 2026-07-11. The three selected DM routes now authenticate and validate on the ASGI loop, select the temporary queue/direct mode, and in queue mode await a Starlette worker that performs the complete synchronous `ServerRuntimeFacade.submit_command()` call and bounded polling wait. The queue action executes through `LanController._tick()` and `InitiativeTracker._lan_apply_action()` on the Tk/headless-root authority thread. The unchanged `CombatService` mutation, force-broadcast work, and final response snapshot complete before `_action_states` is marked completed.

Added exactly:

- `COMMAND_COMBAT_START = "combat_start"`
- `COMMAND_COMBAT_SET_TURN = "combat_set_turn"`
- `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"`

The facade returns the raw service dictionary as `combat_result` and the authority-built final route snapshot as `response_snapshot`. Missing queue, combat, or response-snapshot results are runtime transport failures. Domain `ok: false` results remain raw for the route's existing fixed mapping.

## Files Changed

- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/active/WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation.md`
- `docs/planning/living_docs/combat_mutation_event_loop_containment_minimal_implementation_20260711.md`
- `docs/runtime_reports/combat_mutation_event_loop_containment_minimal_implementation_20260711.md`

No other route, service implementation, public schema, WebSocket protocol, persistence path, cache, resource-pool behavior, startup static fields, or production configuration changed.

## Compatibility Notes

- Start preserves HTTP 200 `{ok, snapshot}`, domain rejection 400, auth 401, unavailable 503, and fixed unexpected failure 500; queue timeout alone maps to 504.
- Set-turn preserves pre-dispatch payload/integer validation, HTTP 200 `{ok, cid, previous_cid, snapshot}`, domain rejection 400, auth 401, unavailable 503, and fixed unexpected failure 500; queue timeout alone maps to 504.
- Next-turn preserves HTTP 200 `{ok, snapshot}`, service-false and invalid-service-snapshot 500 mappings, auth 401, unavailable 503, and fixed unexpected failure 500; queue timeout alone maps to 504.
- `INIT_TRACKER_COMBAT_MUTATION_QUEUE` defaults/fails closed to `queue`; exact `direct` selects the preserved private route-local adapters before enqueue. There is no direct retry after queue submission, failure, or timeout.
- Valid bearer tokens are forwarded; otherwise the existing internal `LanController` admin-token issuer is used only after `_check_dm_auth()` succeeds.

## Validation Results

- `.venv/bin/python -m py_compile server_runtime.py dnd_initative_tracker.py`: passed.
- First `timeout 120s .venv/bin/python -m pytest tests/test_server_runtime.py`: 93 passed and 5 failed because the new authority test fixture assigned the intentionally read-only `LanController.app` property; that early fixture failure also left debug tracing configured to a removed temporary directory.
- One permitted focused test-fix rerun after using the controller's tracker-backed `app` ownership correctly: `95 passed in 1.28s`.
- `timeout 10s git diff --check`: pending final documentation validation.
- `git status --short`: pending final report.

## Remaining Gate

This work item remains **Active** pending the developer-owned controlled smoke gate described above. No server, browser smoke, production action, commit, push, deploy, restart, or SSH action was performed in this implementation pass.

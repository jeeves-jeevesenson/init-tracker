# Combat Mutation Event-Loop Containment Minimal Implementation Report

Date: 2026-07-11

Task: `CODEX-20260711-combat-mutation-containment-implementation-01`

Work item: `WORK-20260710-combat-mutation-event-loop-containment-minimal-implementation`

## Result

Implemented the selected three-route family through the existing `ServerRuntimeFacade` / `LanController._actions` authority queue while preserving synchronous HTTP responses. `run_in_threadpool()` now contains the complete synchronous facade call and bounded queue polling wait. Mutation, existing force-broadcast construction, and the final response snapshot execute before action completion on the Tk/headless-root authority thread.

## Commands And Routes

| Route | Command | Authority service call |
| --- | --- | --- |
| `POST /api/dm/combat/start` | `COMMAND_COMBAT_START = "combat_start"` | `CombatService.start_combat()` |
| `POST /api/dm/combat/set-turn` | `COMMAND_COMBAT_SET_TURN = "combat_set_turn"` | `CombatService.set_turn_here(cid)` |
| `POST /api/dm/combat/next-turn` | `COMMAND_COMBAT_NEXT_TURN = "combat_next_turn"` | `CombatService.next_turn()` |

All commands include the required internal admin, tactical, timeout, trace, and parent-action fields; set-turn additionally includes `cid`. No public payload schema changed.

## Compatibility Evidence

Focused tests cover all three facade successes, raw service result preservation, set-turn `cid`/`previous_cid`, authority-thread execution, snapshot-before-completion ordering, worker offload, auth/validation source ordering, timeout without retry, domain results, transport failures, queue/direct selection and response keys, trace correlation, and one execution per selected command.

The route code retains:

- start: 200 success, 400 domain, 401 auth, 503 unavailable, fixed 500 unexpected, and 504 queue timeout;
- set-turn: 200 success with `cid` and `previous_cid`, pre-worker 400 validation, 400 domain, 401 auth, 503 unavailable, fixed 500 unexpected, and 504 queue timeout;
- next-turn: 200 success, 500 service false, 500 invalid service snapshot, 401 auth, 503 unavailable, fixed 500 unexpected, and 504 queue timeout.

`INIT_TRACKER_COMBAT_MUTATION_QUEUE` defaults and invalid values to `queue`; exact `direct` invokes the preserved private route-local adapters before any enqueue. There is no queue-to-direct fallback.

## Trace Evidence

The focused correlation test exercised all ten new span names under one `trace-http` trace, with command `combat_start`, route `/api/dm/combat/start`, method `POST`, parent action `request-action`, and ASGI/worker/authority thread roles. Queue action IDs remain distinct from the parent HTTP action. Queue wait ends at authority dispatch. LAN and DM schedule spans stop after `run_coroutine_threadsafe()` scheduling; existing fanout spans retain asynchronous recipient, serialized-byte, and fanout reporting.

Serialized byte counts are not available at authority scheduling time without moving serialization or redesigning WebSocket ownership. The narrow implementation therefore reports recipient and schedule duration on schedule spans and leaves byte/fanout metrics on the existing asynchronous broadcast events.

## Validation

Commands run:

```text
.venv/bin/python -m py_compile server_runtime.py dnd_initative_tracker.py
timeout 120s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Results:

- Compilation: passed.
- First focused pytest run: 93 passed; 5 failures caused by the new authority fixture assigning read-only `LanController.app`, with one later existing trace test failing because the early failure left a removed temporary trace path configured.
- Single permitted focused rerun after the fixture correction: 95 passed in 1.28 seconds.
- Final `git diff --check` and `git status --short`: recorded after documentation completion in the final task report.

## Remaining Gate

The implementation is not accepted or complete until the developer-owned controlled smoke gate passes. The active work item and ledger remain active. No commit, push, deploy, restart, browser smoke, SSH, server run, or production action occurred.

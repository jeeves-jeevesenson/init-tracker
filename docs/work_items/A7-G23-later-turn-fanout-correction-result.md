# A7-G23 Later-Turn Fanout Correction Result

Date: `2026-07-16`

Task ID: `CODEX-20260716-a7-accept-later-turn-fanout-g24`

Work item: `WORK-20260715-a7-browser-automation`

Gate: `A7-G23`

Implementation commit: `03597ee`

Terminal classification: `completed-accepted`

## Result

G23 corrected the later-turn connected-player fanout defect proven by G21.
The implementation is accepted at commit `03597ee`. Exactly these files
changed:

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

`assets/web/lan/index.html` remained unchanged. The existing LAN reducer
required no implementation change. The retained G21 browser harness progress
remains committed at `389b0a1` and is the starting point for the future
autonomous browser run.

## Root Cause

1. Throat Goat's End Turn mutation succeeded.
2. Backend authority advanced to Fred `cid=4`.
3. Combat version advanced to `15`.
4. The authoritative snapshot was captured correctly.
5. Player-originated commands had no `_combat_mutation_trace_fields` entry.
6. Tk fallback attribute lookup returned a callable.
7. `_broadcast_state` attempted `dict(callable)`, failed before fanout
   scheduling, and `_lan_force_state_broadcast` swallowed the exception.
8. Connected players therefore received no version-15 personalized envelope.
9. The polling fallback saw no delta because `_last_snapshot` had already
   moved forward.
10. Fred remained rendered on Suppression Gunner `cid=21` with End Turn
    disabled.

## Correction

- `_broadcast_state` reads optional mutation trace metadata directly from
  `self._tracker.__dict__`.
- Tk fallback lookup is no longer used for this optional metadata.
- The captured authoritative snapshot and combat version reach the existing
  personalized WebSocket fanout.
- No polling or alternate synchronization protocol was added.
- The existing LAN reducer required no implementation change.
- Claims, command authority, combat ordering, summons, spells, reconnect
  behavior, and player identity remain preserved.

## Validation

- `py_compile` passed.
- Exactly five focused tests passed in `0.99 seconds`.
- Inline LAN JavaScript syntax validation passed.
- Three-file diff validation passed.
- Focused tests exercised the force-snapshot/version path, scheduled
  personalized fanout, actual LAN reducer, stale-envelope rejection, End
  Turn, claim ownership, and command authority.

## Acceptance Boundary

```text
A7_GATE=A7-G24
A7_STATE=later-turn-fanout-correction-accepted-awaiting-browser-preparation
A7_G23_STATE=completed
A7_G23_RESULT=docs/work_items/A7-G23-later-turn-fanout-correction-result.md
A7_G23_TARGET_COMMIT=03597ee
A7_G23_VALIDATION=pycompile-5-focused-tests-js-syntax-and-diff-check-passed
A7_G24_STATE=not-opened
A7_RETAINED_BROWSER_HARNESS_COMMIT=389b0a1
A7_IMPLEMENTATION_AUTHORIZED=false
A7_TEST_EXECUTION_AUTHORIZED=false
A7_BROWSER_EXECUTION_AUTHORIZED=false
A7_RUNTIME_EXECUTION_AUTHORIZED=false
A7_NETWORK_AUTHORIZED=false
A7_PUSH_AUTHORIZED=false
A7_DEPLOYMENT_AUTHORIZED=false
A7_RESTART_AUTHORIZED=false
A7_SCHEDULER_AUTHORIZED=false
A7_PRODUCTION_AUTHORIZED=false
A7_SERVICE_MUTATION_AUTHORIZED=false
```

All implementation, test, browser, runtime, endpoint, localhost, network,
artifact, retry, push, deployment, restart, scheduler, production, and
service-mutation authorization is closed. A7-G24 is not opened.

The next safe action is orchestrator acceptance and preparation of one
autonomous host-access browser run. That future run begins from the retained
G21 harness implementation already present in the target and must not
reconstruct or discard the retained 35-test harness progress. The
approximately-200-enemy stress scenario remains unopened.

# A7-G19 Player Turn Synchronization Correction Result

Date: `2026-07-16`

Task ID: `CODEX-20260716-a7-accept-player-turn-sync-g20`

Work item: `WORK-20260715-a7-browser-automation`

Gate: `A7-G19`

Implementation commit: `43620b2`

Terminal classification: `completed-accepted`

## Result

G19 corrected the connected-player active-turn synchronization defect proven
by G17. The implementation is accepted at commit `43620b2`. Exactly these
files changed:

- `assets/web/lan/index.html`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

## Root Cause

Combat snapshot versioning was trace-only. Authoritative state and
`turn_update` envelopes lacked an ordering revision, and scheduled broadcasts
rebuilt payloads from mutable cached state rather than their captured
authoritative snapshot. The player client applied every arriving envelope
unconditionally. Stale state could therefore replace a newer active actor.

## Correction

The existing monotonic combat version is now included in initial, recovery,
full-state, and turn-update messages. Authoritative full broadcasts and
polling-channel turn changes advance it, and full broadcasts serialize the
captured authoritative snapshot.

The LAN client rejects lower-version state and rejects unversioned state after
versioned state has been applied. Reconnect resets only the ordering baseline.
Claim revision and ownership remain independent. Turn controls, command
authority, initiative order, player identity, and personalized claim payloads
remain preserved.

## Validation

- `py_compile` passed.
- Exactly three focused tests passed in `0.87 seconds`.
- The three-file diff check passed.
- The inline JavaScript Node syntax check passed.

No browser, server, runtime, endpoint, localhost, network, dependency, push,
deployment, restart, scheduler, production, or service action occurred.

## Acceptance Boundary

All implementation, test, browser, runtime, network, push, deployment,
restart, scheduler, production, and service-mutation authorization is closed.
A7-G20 is not opened.

The next safe action is orchestrator acceptance and preparation of one
autonomous host-access three-surface browser stabilization packet. That future
packet must preserve and commit independently validated harness progress even
when a later application defect causes a controlled stop. The approximately-
200-enemy stress scenario remains unopened.

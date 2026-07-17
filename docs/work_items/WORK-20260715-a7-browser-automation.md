# A7 Browser-Driven Human-Workflow Automation

Date: `2026-07-15 UTC`

Work item: `WORK-20260715-a7-browser-automation`

Active gate: `A7-G23`

State: `later-turn-fanout-correction-authorized`

Approval: `developer-standing-yolo-host-access-2026-07-16`

## Goal

Establish deterministic browser-driven coverage for the accepted A6
three-surface human workflow while preserving explicit, one-shot gate control.
The bounded G7 harness-ordering correction and G10 set-validation correction
are accepted. G11 passed steps 1 through 17, including the reset contract and
all player/enemy additions, then failed at `start-combat` because the still-open
toolbox intercepted normal pointer events. No combat-start HTTP request was
sent, so this proves a harness interaction defect rather than an application
defect. G12 validated the bounded normal-click correction but reached a
controlled stop before browser execution because port 8787 ownership could not
be verified. The candidate harness/test changes were restored to their
starting bytes. G13 then ran in the developer's externally sandboxed
host-access VM and reached a controlled stop after proving that the remaining
fixture mismatch was application-owned and required additional application
file scope. G14 recorded that controlled stop and completed a documentation-only
authorization for one bounded G15 correction. G15 is now completed and
accepted at implementation commit `8abb324`. G17 completed sixteen changed-code
browser attempts and reached a controlled stop after proving an application-
owned live player-surface synchronization defect. G18 accepted that defect and
authorized one later bounded G19 correction. G19 completed that correction and
is accepted at implementation commit `43620b2`. G21 reconstructed and retained
all evidence-validated G17 harness progress, passed the exact 35-node focused
validation, and ran one changed-code browser attempt. Backend authority
advanced from Throat Goat to Fred after a successful player End Turn command,
but Fred's connected claimed surface remained stale on Suppression Gunner and
kept End Turn disabled. G21 therefore stopped at the application-defect
boundary. G22 has now completed the documentation-only authorization for one
later bounded G23 correction and its focused tests in the exact three-file
application/test boundary. G23 is authorized but not started; browser, server,
runtime, endpoint, localhost, and network execution remains closed.

The deterministic workflow remains:

1. Open `/dm`, `/dmcontrol`, and `/`.
2. Add all available roster players through `/dm`.
3. Add one of every black-and-tan enemy through `/dm`.
4. Start combat.
5. Complete at least one full round using both attacks and spells.
6. Assert bounded progress with no hangs and consistent visible state across
   `/dm`, `/dmcontrol`, and `/`.
7. Preserve durable, bounded evidence for terminal coordinator consumption.

The approximately-200-enemy multi-target-spell scenario remains unopened as a
separately approved future stress and latency gate.

## Accepted gate history

A7-G1C added the versioned fixture reset and verification contract and the
deterministic three-surface harness foundation. Its browser, server, endpoint,
and target-runtime execution prohibitions remained in force during that
implementation.

A7-G3 was the first accepted one-shot pilot. It failed because the
three-surface executor was not configured: the harness stopped at the
fail-closed executor placeholder before the existing workflow plan ran. No
application defect was proven. Its accepted terminal result remains recorded
in `docs/work_items/A7-G3-pilot-failure-result.md`, and retry remains
unauthorized.

A7-G4 corrected only the executor wiring and focused fake/mock coverage. The
accepted target commit is `19c0446`. Exactly these implementation files
changed:

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`

The registered executor now runs the existing deterministic three-surface
plan once, preserves no-retry behavior, and records terminal evidence.
Failure-detail formatting preserves the outer terminal reason before bounded
subordinate detail.

The accepted validation is:

- `py_compile` passed;
- exactly 14 focused tests passed in `1.69 seconds`; and
- two-file `git diff --check` validation passed.

The accepted G4 result is
`docs/work_items/A7-G4-executor-correction-result.md`.

A7-G5 ran the corrected executor once and ended in a terminal harness-ordering
failure. The plan clicked `#tab-encounter` before operating the setup-panel
roster controls. `#encounterPlayerList` existed, but was hidden after the
encounter tab replaced the setup panel. This proves a harness-ordering defect,
not an application defect. No retry is authorized.

A7-G7 corrected the browser plan at accepted target commit `83ab9e8`. Exactly
these implementation files changed:

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`

The corrected order is `open-toolbox`, `select-all-roster-players`,
`add-all-roster-players`, `open-encounter`, all nine existing enemy-addition
steps, and all remaining steps in their prior relative order. Every setup step
remains single-pass. The fixture contract, selectors, evidence rules,
no-retry behavior, cleanup behavior, CLI behavior, and headless default remain
unchanged.

The accepted validation is:

- `py_compile` passed;
- exactly 16 focused tests passed in `1.68 seconds`; and
- two-file Git diff validation passed.

The accepted G7 result is
`docs/work_items/A7-G7-ordering-correction-result.md`.

A7-G8 received all nine required unique enemy slugs. It failed solely because
the harness required one exact option order even though the actual and
required identity sets matched. No monster-add request occurred before the
terminal failure. No application defect was proven, G8 consumed its one
authorized attempt, and G8 retry remains unauthorized.

A7-G9 recorded that terminal diagnosis and authorized one bounded G10
correction in exactly:

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`

G10 completed that correction at implementation commit `8db48ee`.
Enemy-option presentation order is now ignored. The harness requires the
exact unique identity set. Missing, extra, and duplicate slugs still fail.
Requested slugs are selected by value, and each enemy-addition step clicks
once. All unrelated behavior remains unchanged.

The accepted validation is:

- `py_compile` passed;
- exactly 20 focused tests passed in `1.74 seconds`; and
- two-file diff validation passed.

The accepted G10 result is
`docs/work_items/A7-G10-enemy-option-set-correction-result.md`.

G11 run `20260716_145717` passed the first 17 steps and failed on its single
`start-combat` step after approximately 30 seconds. The button was visible,
enabled, and stable, but `.toolbox-header` intercepted its pointer events while
the toolbox remained open. No start-combat request was emitted. The durable
result is `docs/work_items/A7-G11-pilot-failure-result.md`; no application
defect was proven.

G13 ran two changed-code browser attempts. The first proved and corrected a
harness race: fixture verification began while the successful combat-start
POST was still in flight. The second awaited HTTP 200 from combat start and
then proved an application fixture defect. The live post-start state contains
the required ten PCs and all nine required enemies plus Owl and Raven summons,
but every enemy exposes `monster_slug: null`. The versioned verifier in
`dnd_initative_tracker.py` requires exactly 19 combatants and uses only
`monster_slug` to classify enemies, so it returned `ui_setup_mismatch` with
actual counts 21 players, zero enemies, and 21 total. The durable result is
`docs/work_items/A7-G13-autonomous-host-stabilization-result.md`.

G14 accepted G13 as a controlled stop that proved the post-combat
fixture-mapping defect and authorized one bounded G15 correction. G14 changed
only the two target ledgers; it did not implement or validate the correction.
The exact G15 file boundary is `dnd_initative_tracker.py` and
`tests/test_server_runtime.py`.

G15 completed the correction at implementation commit `8abb324`. Exactly
these implementation files changed:

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

The root cause was fixture verification relying on nullable `monster_slug`
values and counting Owl and Raven summons as canonical fixture actors.
Configured enemies now fall back to stable `monster_spec.filename` identity,
and canonical players are matched through PC identity and canonical name. Owl
and Raven summons owned by mapped canonical players remain valid runtime units
but are excluded from canonical fixture counts. The canonical expected mapping
remains 10 players, 9 enemies, and 19 actors. Missing, duplicate, incorrectly
mapped, or unexpected actors fail closed. HTTP 409 and `mutated:false`
mismatch behavior remain preserved.

The accepted validation is:

- `py_compile` passed;
- exactly three focused tests passed in `0.38 seconds`; and
- the two-file diff check passed.

The accepted G15 result is
`docs/work_items/A7-G15-runtime-mapping-correction-result.md`.

G17 started from target commit `c0b3ef4` and ended at target result commit
`d450a71`. Sixteen browser attempts ran, and no unchanged-code retry occurred.
Attempts 1 through 15 exposed evidence-backed harness defects and advanced
execution. Focused validation grew from 23 to 35 passing exact nodes. Every
candidate compile and two-file diff check passed. G17 restored the harness/test
candidates under its controlled-stop policy. Future browser packets must
preserve and commit individually validated harness progress when a later
application defect is encountered, rather than discarding all prior proven
corrections.

Attempt 16 proved an application defect at
`player-spell-pc:john-twilight`. Malagrou's enabled End Turn click completed
normally. The debug trace recorded `player_command.end_turn` for Malagrou
`cid=322` with `ok:true`. Backend combat authority advanced to John Twilight
`cid=320`. John's already-connected claimed player surface remained stale on
Malagrou; John's `#endTurn` remained disabled and timed out. Port ownership and
cleanup were positively verified. No push, deployment, scheduler, production,
restart, or service mutation occurred.

G18 inspected the player page's state-application and turn-control ownership,
the backend LAN snapshot/broadcast and player-command seams, and the existing
runtime-test seams. Inspection confirms that the exact three-file future G19
boundary is sufficient and that no additional source or test file is required:

- `assets/web/lan/index.html`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

G18 authorizes one later G19 correction with this exact contract:

1. After one player successfully ends a turn, every already-connected claimed
   player surface must apply the new backend-authoritative active actor.
2. John Twilight's claimed surface must transition from the prior actor to
   John without reload, reconnect, reclaim, or manual interaction.
3. Enabled and disabled turn controls must reflect the newly authoritative
   actor.
4. Preserve claim ownership, combat mutation authority, initiative order,
   WebSocket/session behavior, and existing player commands.
5. Reject or ignore stale or out-of-order client state rather than regressing
   to an older active actor.
6. Do not add polling merely to mask a missing state broadcast.
7. Do not alter combat rules, action economy, spell behavior, turn order, or
   player identity.
8. Add focused coverage proving that an already-connected claimed player
   applies the next active actor after another player ends turn, stale or
   out-of-order state cannot overwrite the newer active actor, and existing
   claim and command behavior remains intact.

G19 completed the correction at implementation commit `43620b2`. Exactly
these files changed:

- `assets/web/lan/index.html`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

Combat snapshot versioning was trace-only. Authoritative state and
`turn_update` envelopes lacked an ordering revision, scheduled broadcasts
rebuilt payloads from mutable cached state rather than their captured
authoritative snapshot, and the player client applied every arriving envelope
unconditionally. Stale state could therefore replace a newer active actor.

The existing monotonic combat version is now included in initial, recovery,
full-state, and turn-update messages. Authoritative full broadcasts and
polling-channel turn changes advance it. Full broadcasts serialize the
captured authoritative snapshot. The LAN client rejects lower-version state
and rejects unversioned state after versioned state has been applied.
Reconnect resets only the ordering baseline. Claim revision and ownership
remain independent. Turn controls, command authority, initiative order,
player identity, and personalized claim payloads remain preserved.

The accepted validation is:

- `py_compile` passed;
- exactly three focused tests passed in `0.87 seconds`;
- the three-file diff check passed; and
- the inline JavaScript Node syntax check passed.

The accepted G19 result is
`docs/work_items/A7-G19-player-turn-sync-correction-result.md`.

## A7-G22 later-turn fanout authorization

G22 is completed as a documentation-only gate. It authorizes one later
bounded G23 implementation and its focused tests in exactly:

- `assets/web/lan/index.html`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

G23 must trace the real authoritative transition through every one of these
stages:

1. successful player end-turn mutation;
2. combat-version advancement;
3. captured authoritative snapshot;
4. per-connection/personalized WebSocket fanout;
5. message version and active actor received by each claimed player;
6. LAN reducer acceptance or rejection; and
7. rendered active actor and turn-control state.

The G23 behavior contract is:

- Every already-connected claimed player must receive and apply every newer
  authoritative active-actor transition.
- This must continue working after multiple actors, enemy turns, summons, and
  earlier player turns, not only the first player-to-player transition.
- Fred's claimed page must transition from Suppression Gunner `cid=21` to Fred
  `cid=4` without reload, reconnect, reclaim, polling, or manual interaction.
- All envelopes representing one authoritative snapshot must carry the
  correct combat version and active actor.
- Personalized claim payload generation must not rebuild or substitute stale
  combat state.
- A stale, lower-version, or otherwise older envelope must not regress the
  active actor.
- Claim ownership and claim revisions must remain independent from combat-
  state ordering.
- Reconnect behavior, command authority, turn order, action economy, combat
  rules, summons, spell behavior, and existing player commands must remain
  preserved.
- Polling must not be added as a workaround.
- The retained G21 browser harness must not be modified in G23.

Required focused G23 coverage must prove:

1. multiple already-connected claimed players receive a later authoritative
   turn transition after several intervening actors;
2. a personalized message for Fred carries the same newer combat version and
   active actor as the authoritative captured snapshot;
3. an older or stale personalized envelope cannot overwrite the later actor;
4. claim ownership and existing command behavior remain intact; and
5. the test exercises the actual server fanout/client reducer contract, not
   merely a search of source text.

```text
A7_GATE=A7-G23
A7_STATE=later-turn-fanout-correction-authorized
A7_G22_STATE=completed
A7_G23_STATE=authorized-not-started
A7_G23_ALLOWED_FILES=assets/web/lan/index.html,dnd_initative_tracker.py,tests/test_server_runtime.py
A7_IMPLEMENTATION_AUTHORIZED=true
A7_TEST_EXECUTION_AUTHORIZED=true
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

G13 is closed at a controlled stop, G14 is complete, G15 is completed and
accepted, G17 is accepted at its controlled stop, G18 is complete, G19 is
completed and accepted, G21 is closed at an application-defect controlled
stop, and G22 is complete. This authorization does not begin G23. Browser,
server, runtime, endpoint, localhost, network, push, deployment, scheduler,
production, restart, and service-mutation action remains unauthorized. The
approximately-200-enemy stress scenario remains unopened.

## Next safe action

The next safe action is one bounded G23 implementation and its focused tests
within the exact authorized three-file boundary. The retained G21 harness/test
progress must remain intact. No browser retry, server/runtime execution, or
network action is authorized.

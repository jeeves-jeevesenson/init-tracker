# A7 Browser-Driven Human-Workflow Automation

Date: `2026-07-15 UTC`

Work item: `WORK-20260715-a7-browser-automation`

Active gate: `A7-G15`

State: `runtime-mapping-correction-authorized`

Approval: `developer-yolo-host-access-2026-07-16`

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
starting bytes. G13 is now running in the developer's externally sandboxed
host-access VM to reapply that correction, perform exact focused validation,
positively verify port ownership, and execute the deterministic workflow. G13
reached a controlled stop after proving that the remaining fixture mismatch is
application-owned and requires additional application-file scope. G14 recorded
that controlled stop and completed a documentation-only authorization for one
bounded G15 correction. G15 is authorized but not started.

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

## Current authorization boundary

```text
A7_GATE=A7-G15
A7_STATE=runtime-mapping-correction-authorized
A7_G13_STATE=controlled-stop
A7_G14_STATE=completed
A7_G15_STATE=authorized-not-started
A7_G15_ALLOWED_FILES=dnd_initative_tracker.py,tests/test_server_runtime.py
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

G13 is closed at a controlled stop, and G14 is complete. The `true`
implementation and test values authorize the later G15 task only; they did not
authorize source/test edits or test execution during G14. Browser, server,
runtime, endpoint, localhost, network, push, deployment, scheduler, production,
restart, and service mutation remain unauthorized.

G15 must satisfy this correction contract:

- Post-combat fixture verification must identify the ten canonical fixture
  players and nine canonical configured enemies through stable
  fixture/runtime identity, not solely through nullable `monster_slug` values.
- Owl and Raven summons are valid runtime units but are not canonical fixture
  actors and must not cause a fixture-count mismatch.
- Verification after successful combat start must accept the canonical
  10-player, 9-enemy, 19-fixture-actor mapping even when total live runtime
  units equal 21.
- Missing, duplicated, or incorrectly mapped canonical fixture actors must
  still fail closed.
- Preserve the fixture schema/version, expected digest, reset behavior, HTTP
  409 fail-closed semantics, and `mutated:false` mismatch behavior.
- Do not alter combat mechanics, summons, initiative, enemy creation, player
  creation, runtime counts, or browser behavior.
- Add focused server-runtime tests for the accepted post-start mapping and at
  least one missing or incorrectly mapped canonical-enemy failure.

## Next safe action

Execute the bounded A7-G15 correction in exactly `dnd_initative_tracker.py` and
`tests/test_server_runtime.py`, then run only its focused authorized tests and
required bounded validation. Do not run a browser, server, runtime, endpoint,
localhost, or network action, and do not open another browser gate.

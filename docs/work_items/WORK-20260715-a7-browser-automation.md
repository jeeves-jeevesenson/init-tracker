# A7 Browser-Driven Human-Workflow Automation

Date: `2026-07-15 UTC`

Work item: `WORK-20260715-a7-browser-automation`

Active gate: `A7-G12`

State: `autonomous-stabilization-controlled-stop`

Approval: `developer-standing-autonomy-2026-07-16`

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
starting bytes.

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

## Current authorization boundary

```text
A7_GATE=A7-G12
A7_STATE=autonomous-stabilization-controlled-stop
A7_G11_STATE=failed
A7_G11_RESULT=docs/work_items/A7-G11-pilot-failure-result.md
A7_G11_FAILURE_STEP=start-combat
A7_G11_ROOT_CAUSE=harness-normal-click-obstructed-by-toolbox-header
A7_G11_APPLICATION_DEFECT_PROVEN=false
A7_G12_STATE=controlled-stop
A7_G12_APPROVAL=developer-standing-autonomy-2026-07-16
A7_G12_RESULT=docs/work_items/A7-G12-autonomous-stabilization-result.md
A7_G12_STOP_CONDITION=port-ownership-cannot-be-verified
A7_G12_BROWSER_RESULT=not-run
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

G12 stopped before browser execution. The verified owned Python/tee children
were stopped and reaped; no unverified process was killed, replaced, or
adopted. All implementation, test, browser, runtime, localhost, and network
authorization is now closed. Push, deployment, scheduler, production, restart,
and service mutation remain unauthorized.

## Next safe action

The orchestrator must first provide an execution environment that can
positively verify port 8787 ownership and keep the owned server and browser in
the same localhost namespace. Before preparing that packet, the
developer/orchestrator must create the pending four-file docs-only commit with
message `Record A7 autonomous stabilization stop.`; Codex could not stage it
because this execution sandbox mounts `.git` read-only. A new bounded packet
may then reauthorize the same two-file normal-click correction, its exact
focused validation, and one headless browser attempt. No implementation,
test, browser, server, runtime, localhost, or network action is currently
authorized.

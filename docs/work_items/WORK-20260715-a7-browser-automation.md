# A7 Browser-Driven Human-Workflow Automation

Date: `2026-07-15 UTC`

Work item: `WORK-20260715-a7-browser-automation`

Active gate: `A7-G10`

State: `enemy-option-set-correction-authorized`

Approval: `developer-explicit-approval-2026-07-15`

## Goal

Establish deterministic browser-driven coverage for the accepted A6
three-surface human workflow while preserving explicit, one-shot gate control.
The bounded G7 harness-ordering correction is accepted. G8 then received the
complete enemy identity set but failed solely on an exact-order harness
requirement. One bounded two-file G10 set-validation correction is authorized
but not started.

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

A7-G9 records that terminal diagnosis and authorizes one bounded G10
correction. G10 may edit exactly:

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`

The correction must validate enemy options by exact unique identity set, not
presentation order. It must fail on any missing, extra, or duplicate slug,
while preserving selection of the requested slug by value and one click. All
other plan steps, the fixture contract, evidence schema, terminal behavior,
no-retry rules, cleanup rules, CLI behavior, and headless default must remain
unchanged. Focused tests must prove reordered complete options pass and
missing, extra, or duplicate options fail.

## Current authorization boundary

```text
A7_GATE=A7-G10
A7_STATE=enemy-option-set-correction-authorized
A7_G8_STATE=failed
A7_G8_RETRY_AUTHORIZED=false
A7_G9_STATE=completed
A7_G10_STATE=authorized-not-started
A7_G10_ALLOWED_FILES=scripts/validation/browser-smoke-harness.py,tests/test_browser_smoke_harness.py
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

This authorization is only a ledger transition for the later G10 task. No
correction was implemented and no focused test was executed during G9. No
browser, server, runtime, endpoint, localhost, network, dependency, artifact,
retry, push, deployment, restart, scheduler, production, service, or cleanup
action occurred.

## Next safe action

The next safe action is the bounded G10 correction in the two allowed files
and its focused tests. Do not implement or test the correction as part of G9,
and do not run a G8 retry.

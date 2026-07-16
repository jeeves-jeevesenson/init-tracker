# A7-G7 Ordering-Correction Result

Date: `2026-07-16 UTC`

Acceptance task: `CODEX-20260716-a7-accept-g7-target`

Target task: `CODEX-20260716-a7-ordering-correction-g7`

Work item: `WORK-20260715-a7-browser-automation`

Gate: `A7-G7`

State: `completed`

## Accepted result

The completed A7-G7 browser-plan ordering correction is accepted at target
commit `83ab9e8` on branch `main`. Exactly these implementation files changed:

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`

G5 failed because the plan opened the Encounter tab before the setup-panel
roster actions. No application defect was proven, and the G5 retry remains
unauthorized.

## Corrected plan order

The accepted setup order is:

1. `open-toolbox`
2. `select-all-roster-players`
3. `add-all-roster-players`
4. `open-encounter`
5. all nine existing enemy-addition steps
6. all remaining steps in their prior relative order

Every setup step remains single-pass. The fixture contract, selectors,
evidence rules, no-retry behavior, cleanup behavior, CLI behavior, and
headless default remain unchanged.

## Target verification and validation

The required Git metadata checks established:

- target branch `main`;
- target HEAD `83ab9e8275bf469b2576b25188b324f99afe7da5`;
- no tracked target changes;
- only the accepted historical untracked paths; and
- commit `83ab9e8` is `Correct A7 browser setup step ordering.` and changes
  exactly the two implementation files named above.

No untracked target file was read. The accepted G7 implementation validation
was:

- `py_compile` passed;
- exactly 16 focused tests passed in `1.68 seconds`; and
- two-file Git diff validation passed.

## Gate record

```text
A7_GATE=A7-G8
A7_STATE=pilot-retry-not-prepared
A7_G5_STATE=failed
A7_G5_RETRY_AUTHORIZED=false
A7_G6_STATE=completed
A7_G7_STATE=completed
A7_G7_RESULT=docs/work_items/A7-G7-ordering-correction-result.md
A7_G7_TARGET_COMMIT=83ab9e8
A7_G7_VALIDATION=pycompile-and-16-focused-tests-passed
A7_G8_STATE=not-opened
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

No browser, server, runtime, endpoint, localhost, network, dependency, pilot,
push, deployment, restart, scheduler, production, or service action occurred
during this documentation-only acceptance. No cleanup action occurred.

## Next safe action

The next safe action is orchestrator acceptance and preparation of one new
one-shot pilot packet. This acceptance neither authorizes nor prepares that
pilot.

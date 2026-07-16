# A7 Browser-Driven Human-Workflow Automation

Date: `2026-07-15 UTC`

Work item: `WORK-20260715-a7-browser-automation`

Active gate: `A7-G5`

State: `pilot-retry-not-prepared`

Approval: `developer-explicit-approval-2026-07-15`

## Goal

Establish deterministic browser-driven coverage for the accepted A6
three-surface human workflow while preserving explicit, one-shot gate control.
The next one-shot pilot packet has not been prepared or authorized.

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

## Current authorization boundary

```text
A7_GATE=A7-G5
A7_STATE=pilot-retry-not-prepared
A7_G3_STATE=failed
A7_G3_RETRY_AUTHORIZED=false
A7_G4_STATE=completed
A7_G4_RESULT=docs/work_items/A7-G4-executor-correction-result.md
A7_G4_TARGET_COMMIT=19c0446
A7_G4_VALIDATION=pycompile-and-14-focused-tests-passed
A7_G5_STATE=not-opened
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

No browser, server, pilot, endpoint, localhost, network, dependency, push,
deployment, restart, scheduler, production, or service action occurred during
the accepted G4 correction or this documentation-only target-ledger
acceptance. No implementation, test execution, browser execution, runtime
execution, network access, push, deployment, restart, scheduler, production,
or service mutation is authorized now.

## Next safe action

The next safe action is orchestrator acceptance and preparation of one new
one-shot pilot packet. Do not authorize or prepare that retry in this target
acceptance.

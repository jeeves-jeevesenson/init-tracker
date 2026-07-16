# A7 Browser-Driven Human-Workflow Automation

Date: `2026-07-15 UTC`

Work item: `WORK-20260715-a7-browser-automation`

Active gate: `A7-G7`

State: `ordering-correction-authorized`

Approval: `developer-explicit-approval-2026-07-15`

## Goal

Establish deterministic browser-driven coverage for the accepted A6
three-surface human workflow while preserving explicit, one-shot gate control.
One bounded harness-ordering correction is authorized for a later G7 pass but
has not started.

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

## Current authorization boundary

A later G7 correction is authorized to edit exactly:

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`

The correction must move `open-encounter` after `add-all-roster-players` and
before enemy setup. It must preserve every other plan step, selector, fixture
contract, evidence rule, no-retry rule, cleanup rule, and the headless
default. Focused tests must prove that roster actions precede
`open-encounter` and that the corrected plan executes each setup step once.
This G6 transition authorizes that work but does not implement it, execute its
tests, or begin G7.

```text
A7_GATE=A7-G7
A7_STATE=ordering-correction-authorized
A7_G5_STATE=failed
A7_G5_RETRY_AUTHORIZED=false
A7_G6_STATE=completed
A7_G7_STATE=authorized-not-started
A7_G7_ALLOWED_FILES=scripts/validation/browser-smoke-harness.py,tests/test_browser_smoke_harness.py
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

No source, test, browser, server, runtime, endpoint, localhost, network,
dependency, artifact, retry, push, deployment, restart, scheduler,
production, or service-mutation action occurred during this documentation-only
transition. Only the later two-file implementation and focused test execution
described above are authorized; all other execution and mutation boundaries
remain closed.

## Next safe action

The next safe action is a separately invoked G7 implementation pass restricted
to the two authorized files and focused test execution described above. Do not
retry G5 or begin browser, server, runtime, endpoint, localhost, or network
execution.

# A7 Browser-Driven Human-Workflow Automation

Date:
2026-07-15 UTC

Work item:
`WORK-20260715-a7-browser-automation`

Active gate:
`A7-G1 browser harness evidence foundation`

State:
`implementation-approved`

Approval:
`developer-explicit-approval-2026-07-15`

Authorized orchestrator task:
`CODEX-20260715-a7-browser-harness-implementation-g1`

## Goal

Extend the existing Python Playwright smoke harness and its focused tests to
represent the accepted A6 three-surface human workflow and produce durable,
coordinator-consumable evidence. Do not launch a browser or server in G1.

The deterministic baseline workflow is:

1. Open `/dm`, `/dmcontrol`, and `/`.
2. Add all available roster players through `/dm`.
3. Add one of every black and tan enemy through `/dm`.
4. Start combat.
5. Complete at least one full round using both attacks and spells.
6. Assert bounded progress with no hangs and consistent visible state across
   `/dm`, `/dmcontrol`, and `/`.
7. Preserve durable, bounded evidence for terminal coordinator consumption.

The approximately-200-enemy multi-target-spell scenario is excluded from G1.
It remains a later, separately approved stress and latency gate.

## Accepted prerequisite evidence

The stale combat mutation implementation item closed at target implementation
commit `0aeb40bed97edd3521ce8afd7e3d9bcdcb5512f5`.

The accepted A6-G3 evidence records a final aggregate of nine focused tests
passed in `0.266s`. The accepted A6-G4 developer smoke opened `/dm`,
`/dmcontrol`, and `/`, added all available roster players and one of every
black and tan enemy, started combat, and completed a full round using varying
attacks and spells across player identities. No hang, incorrect visible
combat progression, or runtime error was reported.

## Allowed implementation files

Edit exactly:

- `scripts/validation/browser-smoke-harness.py`; and
- `tests/test_browser_smoke_harness.py`.

No other target or orchestrator file may be edited during A7-G1
implementation. The target ledger is inspection-only during that
implementation.

## Required A7-G1 behavior

- Preserve all existing harness behavior, scenario identities, CLI behavior,
  assertions, and test coverage.
- Add an explicit deterministic scenario covering `/dm`, `/dmcontrol`, and
  `/`.
- Represent these actions in this exact order:
  1. add all available roster players through the `/dm` surface;
  2. add one of every black and tan enemy through the `/dm` surface;
  3. start combat;
  4. complete at least one round using both attacks and spells; and
  5. assert bounded progress with no hangs and consistent visible state across
     `/dm`, `/dmcontrol`, and `/`.
- Keep the scenario deterministic: declare stable scenario/run identity,
  ordered actors/actions/targets, progress ceilings, expected roster/enemy
  preconditions, and state invariants. Refuse changed or ambiguous
  preconditions rather than silently updating expectations.
- Produce a durable coordinator-consumable evidence shape with fields for:
  - exact scenario, task, gate, approval, attempt, and run identity;
  - terminal `pass`, `fail`, or `recovery` classification with a stable reason
    code and bounded failure detail;
  - required screenshot paths and per-role browser-trace paths;
  - UTC start/end timestamps and monotonic total, startup, navigation,
    per-step, turn, and cleanup timings;
  - server-log and debug-trace paths;
  - reset, fixture-contract, roster, enemy, and precondition evidence;
  - selected port plus ownership, conflict, bind-race, and readiness evidence;
  - context, browser, log-handle, trace, and server cleanup results and final
    disposition;
  - exact validation outcomes and authorization-boundary confirmation; and
  - no automatic retry or next-gate activation.
- Keep all durable artifact paths repository-relative and explicitly record
  when an artifact is inapplicable. Bound failure messages and details so an
  uncontrolled exception, page body, server log, or trace is not copied into
  the terminal record.
- Add deterministic fail-closed port and cleanup behavior. Never attach to,
  replace, restart, terminate, kill, or clean up an unverified process. Kill
  fallback may apply only to the positively identified child process created
  by the harness. Record conflicts and cleanup failure as terminal evidence.
- Ensure cleanup is defined for pass, fail, recovery, exception, timeout, and
  partial-start paths, and treat incomplete cleanup as terminal failure even
  if workflow assertions passed.
- Add or update only focused unit tests that use fakes/mocks and temporary
  paths. Tests must not launch a real browser or server, access an endpoint or
  network, use an existing log/artifact directory, or depend on installed
  browser binaries.
- Keep the approximately-200-enemy multi-target-spell stress scenario entirely
  out of G1.
- If the two allowed files cannot provide the required selectors, reset
  contract, evidence, lifecycle safety, or deterministic behavior, stop and
  report the exact missing requirement rather than expanding scope.

## Exact validation

Run exactly this focused CLI-only test command from the execution repository:

```bash
python tests/test_browser_smoke_harness.py \
  TestBrowserSmokeHarness.test_help \
  TestBrowserSmokeHarness.test_list_scenarios \
  TestBrowserSmokeHarness.test_list_exploration_scenario \
  TestBrowserSmokeHarness.test_multi_round_cli_args \
  TestBrowserSmokeHarness.test_unknown_scenario
```

Then run exactly this bounded diff validation:

```bash
timeout 10s git -C /home/a2-jeeves@iamjeeves.dev/src/init-tracker diff --check -- \
  scripts/validation/browser-smoke-harness.py \
  tests/test_browser_smoke_harness.py
```

Do not run the complete test file: its artifact-attempt test launches Chromium
and makes a localhost request. Do not run compilation, broad tests, a browser,
a server, the target runtime, or any other validation command. If either exact
validation is unavailable or fails, stop without committing.

## Commit policy

A focused target commit is allowed only after both exact validation commands
pass. It must include only the two allowed files and use this exact message:

```text
Implement A7 browser harness evidence foundation.
```

Do not push the commit. If validation fails or the staged scope includes any
other path, do not commit.

## Forbidden scope

- No real browser, server, target runtime, endpoint access, localhost probe,
  external or internal network access, dependency installation, package
  manager action, or generated browser artifact.
- No stress scenario, broad test, compilation command, application code,
  route, template, requirement, lockfile, launcher, specialized LAN smoke, or
  other test edit.
- No target-ledger edit and no orchestrator file edit during implementation.
- No recursive scan, whole-repository grep, old plan, existing log, runtime
  report, untracked-file read, broad discovery, or opportunistic fix.
- No unrelated cleanup, push, deployment, restart, scheduler, production,
  service mutation, credential access, AGY, or Gemini.
- Do not install or change a dependency to compensate for a missing import,
  package, executable, browser, or browser binary.

## Authorization boundary

```text
A7_GATE=A7-G1
A7_STATE=implementation-approved
A7_G0_STATE=completed
A7_G0_RESULT_COMMIT=c9fde65
A7_G0_RESULT=docs/work_items/A7-G0-browser-capability-discovery-result.md
A7_G1_TASK=CODEX-20260715-a7-browser-harness-implementation-g1
A7_G1_TASK_PACKET=docs/agent_tasks/CODEX-20260715-a7-browser-harness-implementation-g1.md
A7_G1_APPROVAL=developer-explicit-approval-2026-07-15
A7_TARGET_IMPLEMENTATION_AUTHORIZED=true
A7_TEST_EXECUTION_AUTHORIZED=true
A7_BROWSER_EXECUTION_AUTHORIZED=false
A7_RUNTIME_EXECUTION_AUTHORIZED=false
A7_DEPENDENCY_INSTALL_AUTHORIZED=false
A7_NETWORK_AUTHORIZED=false
A7_PUSH_AUTHORIZED=false
A7_DEPLOYMENT_AUTHORIZED=false
A7_RESTART_AUTHORIZED=false
A7_SCHEDULER_AUTHORIZED=false
A7_PRODUCTION_AUTHORIZED=false
A7_SERVICE_MUTATION_AUTHORIZED=false
```

The test authorization covers only the exact focused non-browser command in
the authorized orchestrator packet. The implementation authorization covers
only the two allowed target files. Browser/server execution remains forbidden
in G1. Dependency installation, app-code edits, stress testing, push,
deployment, restart, scheduler, production, and service mutation remain
forbidden. No later gate is active.

## Next safe action

Run only `CODEX-20260715-a7-browser-harness-implementation-g1` under its
explicit approval and exact task packet. Stop after bounded validation, the
conditional focused target commit, status capture, and the final report. Do
not launch a browser or server and do not activate a later gate.

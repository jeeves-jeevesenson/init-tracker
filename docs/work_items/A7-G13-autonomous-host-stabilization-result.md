# A7-G13 Autonomous Host Stabilization Result

Date: `2026-07-16`

Task: `CODEX-20260716-a7-autonomous-host-stabilization-g13`

Starting commit: `2db10ab0fd83bc702c14b0c7d5fa97f6bf9aba27`

State: `controlled-stop`

Terminal browser result: `fail`

## Authorization and baseline

The developer explicitly authorized G13 host-access implementation, exact
focused validation, positively verified same-user localhost-server management,
headless browser execution, evidence inspection, evidence-backed harness
corrections, durable reporting, and one terminal commit. The verified baseline
was branch `main` at
`2db10ab0fd83bc702c14b0c7d5fa97f6bf9aba27` with no tracked changes.

## Corrections and focused validation

The G12 correction was reapplied within the single `start-combat` plan step:
one normal Playwright click on `#closeToolboxBtn` cleared the proven obstruction
before one normal Playwright click on `#startCombatBtn`. No forced, DOM,
dispatched-event, JavaScript, or coordinate click was used.

Initial validation passed:

- `timeout 30s .venv/bin/python3 -m py_compile scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py` — passed;
- the exact required 22-node pytest invocation — `22 passed in 1.68s`; and
- `timeout 10s git diff --check -- scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py` — passed.

Attempt 1 proved an additional harness race. The ordinary combat-start click
returned before its asynchronous request completed, allowing the versioned
verification request to overlap the start mutation. The bounded correction
made the same `start-combat` step await the exact successful
`POST /api/dm/combat/start` response before returning. One focused test,
`test_three_surface_start_combat_waits_for_successful_response_before_returning`,
was added.

Post-correction validation passed:

- the same py-compile command — passed;
- the existing exact 22-node pytest invocation — `22 passed in 1.72s`;
- the new exact pytest node — `1 passed in 0.20s`; and
- the same two-file diff check — passed.

Per the controlled-stop policy, all unaccepted harness/test candidate changes
were restored to their exact starting bytes. `git diff --exit-code --
scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py`
passed.

## Browser attempts

### Attempt 1: `20260716_155328`

Terminal classification: `fail` / proven harness race.

Steps 1 through 19 passed, including all roster/enemy setup, the corrected
normal combat-start click, and the verification POST. Step 20,
`validate-complete-runtime-mappings`, failed with `ui-setup-mismatch` because
verification raced combat start:

- combat start request began at `2026-07-16T20:53:38.800Z`;
- fixture verification began at `2026-07-16T20:53:38.977Z`; and
- combat start returned HTTP 200 at `2026-07-16T20:53:39.192Z`.

No unchanged-code retry occurred. The response-wait correction and focused
validation preceded attempt 2.

### Attempt 2: `20260716_155630`

Terminal classification: `fail` / application defect; controlled stop.

Steps 1 through 19 again passed. The corrected combat-start request began at
`2026-07-16T20:56:40.822Z` and returned HTTP 200 at
`2026-07-16T20:56:41.073Z`. Fixture verification began later, at
`2026-07-16T20:56:41.284Z`, proving the harness no longer raced the request.
Step 20 still received HTTP 409 and failed with `ui-setup-mismatch`.

The exact fixture response expected 10 players, 9 enemies, and 19 total, but
reported 21 players, 0 enemies, and 21 total. A read-only live DM snapshot
proved the normal post-start state actually contained all ten required PCs,
all nine required Black-and-Tan enemies with `role: enemy`, and the legitimate
Owl and Raven start summons. Every enemy exposed `monster_slug: null`.

The application verifier `_black_tan_verify_contract_state()` in
`dnd_initative_tracker.py` classifies combatants solely by `monster_slug` and
requires the exact 10/9/19 count. It therefore cannot accept the normal
post-start state. This is an application fixture defect, not another harness
defect. Correcting it requires additional tracked scope in:

- `dnd_initative_tracker.py`; and
- `tests/test_server_runtime.py` for focused fixture-contract coverage.

No application file was edited, and no third browser attempt ran.

## Evidence

- Server log: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_smoke-server_20260716-155209.log`
- Debug trace: `logs/debug-trace-20260716-155209.jsonl`
- Browser artifact root: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/`
- Attempt 1 summary: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/black-tan-three-surface-workflow/20260716_155328/summary.json`
- Attempt 1 Markdown summary: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/black-tan-three-surface-workflow/20260716_155328/summary.md`
- Attempt 1 browser trace: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/black-tan-three-surface-workflow/20260716_155328/browser-trace.zip`
- Attempt 2 summary: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/black-tan-three-surface-workflow/20260716_155630/summary.json`
- Attempt 2 Markdown summary: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/black-tan-three-surface-workflow/20260716_155630/summary.md`
- Attempt 2 browser trace: `logs/smoke/CODEX-20260716-a7-autonomous-host-stabilization-g13_browser-artifacts/black-tan-three-surface-workflow/20260716_155630/browser-trace.zip`
- Each attempt directory also contains the DM control trace and all ten player-role traces. Neither attempt produced a screenshot before its terminal fixture barrier.

## Port ownership and cleanup

Host preflight found no listener on port 8787. G13 started one owned process
group, PGID `61040`: shell PID `61040`, Python PID `61041`, and tee PID `61042`.
The Python process was owned by user `a2-jeeves@iamjeeves.dev` / UID
`1462001134`; its resolved executable was `/usr/bin/python3.13`, its command was
`.venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787`, and its working
directory was `/home/a2-jeeves@iamjeeves.dev/src/init-tracker`. `ss` attributed
the `0.0.0.0:8787` listener to PID `61041`, and `/dm` returned HTTP 200.

After browser termination and application-defect classification, the same
identity evidence was reverified. The owned session received Ctrl+C; no
SIGKILL or unverified process action occurred. The shell, Python, and tee
processes terminated, `ps` showed none remaining, and `ss` proved port 8787
free.

## Final boundary

```text
A7_STATE=autonomous-host-stabilization-controlled-stop
A7_G13_STATE=controlled-stop
A7_G13_RESULT=docs/work_items/A7-G13-autonomous-host-stabilization-result.md
A7_IMPLEMENTATION_AUTHORIZED=false
A7_TEST_EXECUTION_AUTHORIZED=false
A7_BROWSER_EXECUTION_AUTHORIZED=false
A7_RUNTIME_EXECUTION_AUTHORIZED=false
A7_NETWORK_AUTHORIZED=false
```

Push, deployment, restart, scheduler, production, and service mutation remained
unauthorized and did not occur. The approximately-200-enemy stress scenario
remained unopened.

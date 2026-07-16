# A7-G12 Autonomous Stabilization Result

Date: `2026-07-16`

Task: `CODEX-20260716-a7-autonomous-stabilization-g12`

Starting commit: `22013960c9c8291dace37c8ea3eb3d2218c2fc76`

State: `controlled-stop`

## Authorization and inherited evidence

The developer standing authorization dated 2026-07-16 permits bounded G12
harness/test correction, focused validation, an owned localhost server,
headless three-surface browser runs, evidence inspection, durable reporting,
and one focused commit after terminal pass.

G11 run `20260716_145717` passed steps 1 through 17 and failed at the single
`start-combat` step because the still-open `.toolbox-header` intercepted
pointer events intended for visible, enabled, stable `#startCombatBtn`. No
combat-start HTTP request was sent; no application defect was proven.

## Attempts

No G12 browser attempt ran. The stop occurred during owned-server preflight,
before the exact browser command was executed and before any G12 browser
artifact timestamp directory was created.

## Candidate correction 1

Implemented: clear the proven obstruction through the existing
`#closeToolboxBtn` normal UI control, then issue one normal Playwright click on
`#startCombatBtn` within the single `start-combat` plan-step execution. Add the
two required focused tests proving interaction order and forbidding forced or
DOM-bypass clicks.

Validation passed:

- `timeout 30s .venv/bin/python3 -m py_compile scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py`
- the exact G10 20-node pytest selection plus the two required G12 node IDs: `22 passed in 1.71s`
- `timeout 10s git diff --check -- scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py`

The correction preserved exactly one `start-combat` plan step and used the
existing `#closeToolboxBtn` normal UI control before one ordinary Playwright
click on `#startCombatBtn`. It introduced no forced click, evaluate-click, or
dispatched click event. Per the controlled-stop policy, the candidate harness
and test changes were restored to their exact starting bytes. A targeted
`git diff --exit-code` confirmed both files are unchanged from the starting
commit.

## Controlled-stop evidence

The first owned server session reached tracker initialization and was stopped
through its own session before browser execution when the tooling's isolated
PID/network namespaces made cross-session ownership verification impossible.
A second persistent owned shell was then used so the server and planned
browser execution would share localhost. Within that shell:

- owned shell PID: `2`;
- owned Python server PID: `5`;
- owned tee PID: `6`;
- the child command lines and common parent were recorded before browser execution;
- readiness probing returned HTTP `000`; and
- the server reported `could not bind on any address out of [('0.0.0.0', 8787)]`.

The command sandbox's TCP table did not expose the occupying listener, so no
PID or ownership could be established for it. This triggered the defined
`port ownership cannot be verified` stop condition. No unverified process was
killed, replaced, or adopted.

Only verified owned PID `5` was sent SIGINT. It logged LAN shutdown, exited,
and was reaped; tee PID `6` exited after EOF. A final direct-child process
listing showed neither child remained. The persistent owned shell then exited
normally.

Generated evidence:

- `logs/smoke/CODEX-20260716-a7-autonomous-stabilization-g12_smoke-server_20260716-153235.log`
- `logs/smoke/CODEX-20260716-a7-autonomous-stabilization-g12_smoke-server_20260716-153349.log`
- `logs/debug-trace-20260716-153235.jsonl`
- `logs/debug-trace-20260716-153349.jsonl`

There is no G12 browser summary, screenshot, browser trace, role trace, fixture
evidence, or ordered browser timing set because no browser attempt ran.

## Required next scope

The orchestrator must provide an execution environment that can positively
identify any listener on port 8787 and keep the owned server and browser in the
same localhost namespace. Port 8787 must then be proven free without killing,
replacing, or adopting an unverified process. A new bounded authorization may
reapply the already validated two-file correction and its two focused tests,
rerun the exact compile/22-node validation, start one ownership-verified
server, and execute one headless three-surface workflow attempt.

No implementation, test, browser, runtime, localhost, network, push,
deployment, scheduler, production, restart, or service-mutation action remains
authorized after this stop.

## Commit disposition

`timeout 10s git diff --check` passed for the durable docs. Codex then
attempted to stage exactly the four allowed docs for the required commit. Git
failed before staging because `.git` is mounted read-only and it could not
create `.git/index.lock`. No index or commit mutation occurred. The starting
and resulting commit therefore remain
`22013960c9c8291dace37c8ea3eb3d2218c2fc76`.

The developer/orchestrator must create the pending docs-only commit with exact
message `Record A7 autonomous stabilization stop.` before opening the next
bounded runtime packet.

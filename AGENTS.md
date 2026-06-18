# Repository guidance for AGY (Antigravity CLI) and other agents

The primary agent executor for this repository is **AGY (Antigravity CLI)**.
Gemini and Claude are secondary tools for broad analysis or migration support.

## AGY Token Budget & Discipline

To maintain focus and minimize token burn:
- **No broad repo scans:** Do not scan the whole repo unless explicitly allowed.
- **Read-first:** Read only named files first.
- **Source preference:** Prefer `docs/work_items/current_work.md` and active
  task documents over historical or archived docs.
- **Minimal inspection:** Do not inspect `majorTODO.md`, old plans, or
  historical reports unless they are named in the task packet.
- **Log efficiency:** Use `grep`, `head`, `tail`, or `sed` for logs instead
  of reading full log files.
- **Scope limit:** Identify the minimal file list needed before editing.
- **Stop early:** Stop immediately after bounded validation/report.

## Active production recovery

Active production recovery work is controlled by `docs/production_recovery_living_doc_20260526.md`.
For recovery gates, that document overrides `majorTODO.md` and older docs when they differ.
Do not mix gates. Do not commit, push, deploy, SSH, or restart services unless explicitly asked.
Browser UI readiness requires an inline JavaScript syntax check plus browser smoke; edits to `assets/web/dmcontrol/index.html` require the same inline JS syntax check as other browser HTML assets.

## Production Operations

Production server updates and environment details are governed by:
- `docs/agent_ops/production_update_runbook.md` (Sanitized procedures)
- `docs/local/production_environment.md` (Local-only environment details)

Agents must follow the runbook and must not attempt production deployment,
restarts, or code pushes without explicit instruction.

## Mission

This repository is in a broad migration away from a Tkinter/canvas-heavy desktop host toward a production-ready, web-first, backend-owned system.

Treat this repo as migration/extraction work first:
- move authority out of monolithic desktop-owned handlers
- keep rendering/client concerns separate from backend authority
- prefer explicit service seams and contracts
- do not optimize for preserving Tk/desktop behavior as the end-state

The final target is not a better desktop shell. The final target is a web-first product with backend-owned combat/session authority.

## Source of truth

Before making strong claims:
- inspect the current repository state
- use current code plus `majorTODO.md` as source of truth
- trust code/tests over stale docs when they disagree
- update `majorTODO.md` honestly when the repo state has changed

Do not invent:
- missing branches
- stale TODO items
- file paths or systems that are not present in the repo

If a TODO/reference is stale, say so plainly and fix the tracker instead of fabricating compatibility work.

## Working style

Default to:
- minimal repo inspection
- one broad, coherent, bounded pass
- focused validation
- clear end-of-pass reporting

Prefer:
- broad family extraction over tiny seam polish
- smallest complete scoped solution, not smallest diff
- one real ownership move per pass
- stable delegation/routing patterns across adjacent families

Avoid:
- repo-wide wandering
- over-planning when scope is already implementation-ready
- micro-cleanup passes that do not materially reduce inline ownership
- unnecessary renames, comment cleanup, or abstraction churn

## Migration pattern to prefer

When extracting a player-command family, prefer this shape when it fits the repo:

1. identify the coherent inline family in `_lan_apply_action()`
2. add family command constants and request/result contract builders in `player_command_contracts.py`
3. add family dispatch + handlers in `player_command_service.py`
4. move deep logic into named tracker helper methods if needed for compatibility
5. keep `_lan_apply_action()` as delegation glue for the migrated family
6. add focused tests for contracts/dispatch where needed
7. update `majorTODO.md` honestly

Temporary compatibility is acceptable when it helps land the migration safely and quickly.

## Architecture direction

Prefer:
- backend-owned authority
- explicit contracts
- canonical state models
- testable helper/service seams
- removing or shrinking monolithic ownership hotspots

Do not:
- spread tracker/desktop coupling into new code
- add new desktop-first fallback paths unless absolutely required for a safe bounded pass
- keep long-lived dual ownership when a slice has already been migrated

## Scope discipline

When a task is already implementation-ready:
- do not ask the user to restate requirements
- do not turn a code task into a planning-only answer
- do not stop after the first narrow branch if adjacent in-scope branches are clearly part of the same family

Keep changes tightly scoped to the requested family or hotspot.
Do not widen into unrelated DM/map/framework work unless one narrow compatibility touch is truly required.

## Validation expectations

Use focused validation proportional to the pass.

Default validation:
- `python3 -m py_compile` on edited Python files
- focused `python3 -m unittest` coverage for the migrated family
- command-contract / allowlist tests if touched
- adjacent focused regression tests when the family shares runtime paths

Do not default to indiscriminate whole-repo test sweeps unless the risk clearly justifies it.

Be explicit about:
- real regressions
- pre-existing failures
- environment blockers such as missing dependencies or missing pytest

## Reporting expectations

At the end of a substantial pass, report:
- files inspected
- files changed
- exactly which branches/commands were migrated
- what still remains inline in `_lan_apply_action()`
- what handlers / dispatchers / contracts were introduced or changed
- what tests were run and their results
- what remains rough or risky
- exactly how `majorTODO.md` was updated
- the single best next broad pass

Do not claim a phase is complete unless code and focused validation support that claim.

## Guardrails

- Do not commit unless explicitly asked.
- Do not push unless explicitly asked.
- Do not rename `dnd_initative_tracker.py`.
- Do not break saved-data or YAML compatibility unless explicitly scoped.
- Keep reconnect, claims/auth, hidden-information handling, and persistence safety intact.
- Do not rewrite the map/tactical layer first unless the task explicitly requires it.
- Do not preserve desktop-first behavior as an end-state goal.

## Mandatory browser-asset JavaScript syntax check

Any pass that edits `assets/web/dm/index.html` or `assets/web/lan/index.html` must run an inline JavaScript parse/syntax check before reporting success.

Python tests are not enough for these files. Browser parse failures such as `Unexpected token '}'` or `Identifier '<name>' has already been declared` are blockers.

The end-of-pass report must include the exact JS syntax-check command and result. Do not claim browser readiness if the check was skipped, unavailable, or failed.

Preferred check: extract inline `<script>` blocks from the edited HTML file(s) and run `node --check` against the extracted JavaScript.

## Validation discipline

Agents must not run unbounded tests. Use `scripts/agent_gate_validate.sh <gate-id>` or an explicit `timeout` wrapper for targeted diagnostics.

Required gate validation is enough for an agent report. If required validation passes, stop and report instead of running broad extra suites for more confidence.

Extra tests are allowed only when they are targeted to a specific failure, timeout-bounded, and named in the final report.

Known websocket tests must never be run without a timeout.

Browser smoke is developer-owned and is not replaced by extra Python tests.

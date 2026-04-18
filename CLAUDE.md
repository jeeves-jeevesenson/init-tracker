# Claude project instructions

## Mission

This repository is in a broad migration away from a Tkinter/canvas-heavy desktop host toward a production-ready, web-first, backend-owned system.

Treat work here as migration/extraction work first:
- move authority out of monolithic desktop-owned handlers
- favor explicit service seams and contracts
- keep client/rendering concerns separate from backend authority
- do not optimize for preserving Tk/desktop behavior as the end-state

The final target is not a cleaned-up desktop shell. The final target is a web-first product with backend-owned combat/session authority.

## Source of truth

Before making strong claims:
- inspect the current repository state
- use current code plus `majorTODO.md` as source of truth
- trust code/tests over stale docs when they disagree
- update `majorTODO.md` honestly when the repo state has changed

Do not invent:
- nonexistent command branches
- stale TODO items as if they are live
- file paths or architecture that are not present in the repo

If a TODO/reference is stale, update the tracker instead of fabricating a compatibility path.

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

## Preferred migration pattern

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
- shrinking monolithic ownership hotspots

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

---
name: backend-family-extraction
description: Use this skill when extracting a coherent inline backend/player-command family out of dnd_initative_tracker.py and into PlayerCommandService with explicit contracts, focused validation, and an honest majorTODO.md update.
license: Proprietary - repository local use only
---

# Backend family extraction

Use this skill when the task is to move a **bounded inline command family** out of `_lan_apply_action()` and behind `PlayerCommandService` / explicit contracts.

This repository is in a migration from a Tkinter/canvas-heavy desktop host toward a **web-first, backend-owned** system. The point of these passes is not polish. The point is to reduce inline ownership and move authority into stable backend seams.

## When this skill applies

Use this skill for tasks like:

- extracting a bounded player-command family from `_lan_apply_action()`
- moving adjacent command branches behind `PlayerCommandService`
- adding explicit request/result contract builders for a migrated family
- updating `majorTODO.md` after a substantial migration pass

Examples:
- movement/action family
- wild-shape family
- spell-launch family
- AoE manipulation family
- bard/glamour specialty family
- summon/echo family

Do **not** use this skill for:
- broad framework rewrites
- UI-first tasks
- map rendering rewrites unless explicitly scoped
- generic bugfixes that are not family extraction work

## Primary goal

For a bounded family extraction pass:

1. identify the **real live inline family** in `_lan_apply_action()`
2. move transport/authority ownership behind `PlayerCommandService`
3. add explicit contracts in `player_command_contracts.py`
4. keep `_lan_apply_action()` as delegation glue for the migrated family
5. preserve user-visible behavior as much as practical
6. update `majorTODO.md` honestly
7. stop when the family is materially more backend-owned and review-ready

## Source of truth

Before making strong claims:

- inspect the current repo state
- trust current code and focused tests over stale docs
- use `majorTODO.md` as the migration tracker, not as permission to invent nonexistent branches

If a TODO entry is stale:
- do **not** invent a compatibility path just because the tracker mentions it
- extract the real live family in code
- update `majorTODO.md` honestly to match repo reality

## Default workflow

### 1) Inspect minimally

Inspect only the files needed for the targeted family. Usually:

- `dnd_initative_tracker.py`
- `player_command_service.py`
- `player_command_contracts.py`
- `majorTODO.md`
- the most relevant focused tests for the family

Prefer targeted search over broad repo scanning.

Good search pattern:
- find the inline branches in `_lan_apply_action()`
- find the current service-dispatch pattern for adjacent already-migrated families
- find existing contract-builder patterns for adjacent families
- find focused tests that already cover the same runtime path

### 2) Define the family honestly

Extract the **largest coherent bounded family** you can land in one pass.

Prefer:
- one broad family dispatcher / handler shape
- adjacent branches that truly belong together
- a material ownership reduction over a tiny seam-only cleanup

Avoid:
- dragging unrelated branches into scope
- reopening already-stable migrated families
- mixing in map/UI/DM work unless one narrow compatibility touch is required

### 3) Apply the repository migration pattern

When it fits the repo, use this shape:

#### Contracts
In `player_command_contracts.py`:
- add `*_COMMAND_TYPES`
- add request field sets if needed
- add request/result contract builders for the family
- mirror the style of adjacent existing families

#### Service seam
In `player_command_service.py`:
- add a family dispatcher
- add per-command handlers or family handlers
- build request contracts there
- return explicit dispatch results
- keep authority-entry behavior there rather than backsliding into tracker-owned transport logic

#### Tracker compatibility layer
In `dnd_initative_tracker.py`:
- replace inline `_lan_apply_action()` branches with a single family delegation branch
- move deep runtime logic into named tracker helper methods if needed
- keep tracker helpers as temporary compatibility adapters when that is the fastest safe migration path

This repository is allowed to keep domain-heavy tracker helpers temporarily. The goal of these passes is to move the **authority boundary** first, not to perfect every internal engine in the same run.

### 4) Preserve behavior that matters

Preserve existing user-visible behavior as much as practical, especially:
- validation/gating
- action/resource deductions
- prompt kickoff/resume behavior if relevant
- messaging / toasts / battle-log side effects
- rebuild / state-broadcast side effects
- persistence / YAML compatibility where relevant
- claim/auth/reconnect safety

Do not preserve legacy desktop-first ownership as an end-state goal.

### 5) Validate proportionally

Required validation for a non-trivial family pass:

- `python3 -m py_compile` on edited Python files
- focused `python3 -m unittest` suites for the migrated family
- command-contract / allowlist tests if touched
- adjacent focused regression tests when the family shares runtime paths

Prefer focused tests first.
Do **not** default to indiscriminate whole-repo sweeps unless risk clearly justifies it.

If `pytest` is unavailable, say so clearly and proceed with focused `unittest` / compile validation.

### 6) Update majorTODO.md honestly

After a substantial pass, update `majorTODO.md` to reflect:
- what family landed
- which command branches were migrated
- the new service/contract boundary
- what still remains inline
- the single best next broad pass

Do not leave stale “next pass” guidance behind if the repo state has moved.

## Guardrails

- Do not commit unless explicitly asked.
- Do not push unless explicitly asked.
- Do not rename `dnd_initative_tracker.py`.
- Do not invent stale command branches.
- Do not broaden into unrelated DM/map/framework work unless truly required.
- Do not preserve Tk/desktop ownership as an end-state goal.
- Do not stop after tiny seam work if a real bounded adjacent family is clearly in scope.
- Do not turn an implementation-ready migration task into a planning-only answer.

## Completion report format

At the end of the pass, report:

- files inspected
- files changed
- exactly which branches/commands were migrated
- what still remains inline in `_lan_apply_action()`
- what handlers / dispatchers / contracts were introduced or changed
- what tests were run and their results
- what remains rough or risky
- exactly how `majorTODO.md` was updated
- the single best next broad pass

## Repo-specific reminders

- This repo is trying to replace the old desktop authority path, not perfect it.
- Broad family extraction is preferred over micro-polish.
- The right stopping point is usually: “the bounded family is materially more backend-owned and review-ready,” not “every internal helper is perfect.”

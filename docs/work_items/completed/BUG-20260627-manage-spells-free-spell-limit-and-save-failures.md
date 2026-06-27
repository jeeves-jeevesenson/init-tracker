# BUG-20260627-manage-spells-free-spell-limit-and-save-failures

## Status
Completed

## Source report
`docs/bug_reports/inbox/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md`

## Goal
Recover Manage Spells reliability on the LAN Player Page `/` for free spell add/remove behavior and save persistence failures.

## Initial scope
Evidence capture first. Do not assume the Eldramar free-spell failures and Ctihiya save failure share one root cause.

## Required evidence before implementation
- Current backend/log evidence covering Manage Spells add/remove/save attempts.
- Browser console errors from an affected player browser if available.
- Exact visible UI behavior: disabled button, error message, no-op, spinner, stale refresh, rollback, or failed persistence.
- Character and spell names involved in the Eldramar free-spell add/remove case.
- Whether Ctihiya save failure reproduces on a valid small change.

## Allowed next action
Create one bounded AGY evidence/diagnosis task for this bug, or collect developer runtime evidence manually.

## Do not do
- Do not start broad Manage Spells refactors.
- Do not assume all characters are affected.
- Do not assume frontend-only or backend-only root cause.
- Do not revive old spell/ranged attack work.


## Completion / closeout
Completed on 2026-06-27.

Implemented targeted Manage Spells repairs:
- Free spell add/prepare flow no longer blocks solely because the normal known/prepared count is already at or over max.
- Free prepared spells can be selected and removed/unprepared through Manage Spells when they are user-managed free spell entries.
- Cyrillic/Unicode player profile lookup and save behavior was repaired without renaming character files or editing character YAML.

Validation / evidence:
- AGY scoped repair completed in `AGY-20260627-manage-spells-repair-01`.
- `dnd_initative_tracker.py` py_compile passed.
- `tests/test_spellbook_free_spells.py` passed via unittest fallback because pytest was unavailable in the environment.
- `scripts/agent_gate_validate.sh A0` passed.
- `git diff --check` passed.
- Developer browser smoke passed for Eldramar free spell add/remove, Cyrillic/Ctihiya save persistence, and normal non-free limit behavior.

Related reports:
- Evidence report: `BUG-20260627-manage-spells-free-spell-limit-and-save-failures-evidence-AGY-20260627-manage-spells-evidence-01.md`
- Repair report: `BUG-20260627-manage-spells-free-spell-limit-and-save-failures-repair-AGY-20260627-manage-spells-repair-01.md`

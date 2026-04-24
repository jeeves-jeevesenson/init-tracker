# Repo Cleanup Plan

## Purpose

This file is the temporary working plan for cleaning up the repo structure without breaking the app.

The goal is not to make the repo pretty in one broad pass. The goal is to make cleanup safe, staged, testable, and finite.

This file should be updated by each cleanup pass. When the cleanup workstream is complete, remove this file.

---

## Cleanup Principles

- Do not move or delete files based on vibes.
- Start with audit/classification before moving anything.
- Preserve working app behavior.
- Keep cleanup passes small and reversible.
- Do not mix app-data normalization with repo-structure cleanup.
- Do not touch gameplay/runtime logic unless a cleanup move requires a tiny import/path fix.
- Do not clean `Items/`, `Spells/`, `Monsters/`, `players/`, or `presets/` during the initial repo-structure cleanup.
- If a file’s purpose is unclear, classify it as `unknown` instead of guessing.
- Every move/delete pass must include validation.
- Each pass must update this file with what changed and what remains.

---

## Classification Labels

Use these labels when auditing files:

- `keep-root` — belongs in the repo root as an entrypoint, config, top-level doc, or core module.
- `move-to-scripts` — executable/helper script that should live under `scripts/`.
- `move-to-docs` — documentation, notes, planning, or human-facing reference material.
- `move-to-tests` — test helper, fixture, or validation-only asset.
- `archive` — historically useful but not active; move under an archive location if retained.
- `delete-candidate` — appears unused/dead, but must be validated before deletion.
- `unknown` — purpose unclear; needs user decision or deeper inspection.

---

## Intended End State

The repo cleanup workstream is done when:

- Root contains only intentional top-level docs, config, app entrypoints, core modules, and data directories.
- Script-like files are grouped under `scripts/` with clear names and/or a `scripts/README.md`.
- Historical notes and obsolete planning files are moved under `docs/archive/` or deleted.
- The working installer and README installation docs are current and do not reference stale workflows.
- No known broken setup/install scripts remain.
- No files remain classified as `unknown`.
- Tests and basic launch/import checks pass after moves.
- This `cleanupplan.md` file is removed.

---

## Current Scope

Initial cleanup is limited to repo structure and maintenance clutter.

In scope:

- repo root file audit
- script/helper file classification
- install/setup/bootstrap cruft
- docs/planning-note organization
- obsolete or duplicate maintenance files
- README references to moved/deleted files
- lightweight import/path fixes caused by file moves

Out of scope for initial cleanup:

- gameplay/runtime feature work
- spell/backend implementation
- player YAML updates
- item/spell/monster data normalization
- tactical map UI changes
- broad refactors
- migration architecture work
- performance work unless cleanup exposes a broken script/path

---

## Phase 1 — Audit Manifest

Status: `complete`

Goal:

Create an audit/classification table before moving or deleting anything.

Deliverable:

- `docs/repo_cleanup_manifest.md`

Required contents:

- all root-level files
- all script-like files under `scripts/`
- questionable docs/planning files
- current path
- classification label
- proposed final path
- evidence/references found
- validation needed before move/delete
- risk/notes

Validation:

- confirm every root-level file is represented
- confirm every script-like file under `scripts/` is represented
- no files moved or deleted in this phase

---

## Phase 2 — Root Hygiene

Status: `complete`

Goal:

Use the manifest to clean the repo root.

Allowed actions:

- move obvious scripts to `scripts/`
- move obvious docs/notes to `docs/`
- move historical material to `docs/archive/`
- update references caused by those moves
- delete only high-confidence dead files already marked `delete-candidate`

Constraints:

- no app behavior changes
- no data directory cleanup
- no broad import restructuring

Validation:

- run syntax/import checks needed for any moved Python files
- run targeted tests if imports/references changed
- grep README/docs/scripts for stale moved paths
- update this file with completed moves and remaining root clutter

---

## Phase 3 — Scripts Organization

Status: `complete`

Goal:

Make `scripts/` understandable and safe to use.

Target shape may include:

- `scripts/install/`
- `scripts/dev/`
- `scripts/validation/`
- `scripts/debug/`
- `scripts/migration/`
- `scripts/archive/`

Deliverables:

- organized script paths
- `scripts/README.md` describing active scripts and obsolete/archive status

Constraints:

- do not rewrite working scripts unless they are broken
- do not migrate to a new package/tooling system
- preserve the currently working installer

Validation:

- shell syntax validation for shell scripts where applicable
- Python compile checks for Python scripts
- README/docs references updated
- stale script paths removed

---

## Phase 4 — Docs and Planning Cleanup

Status: `in progress`

Goal:

Separate active docs from historical planning clutter.

Expected shape:

- root `README.md` remains user-facing
- `AGENTS.md` and `CLAUDE.md` remain standing agent context
- active planning stays in current active planning file(s)
- historical notes move to `docs/archive/`
- obsolete TODO/planning files are deleted only after confirmation

Validation:

- root docs still explain current workflows
- no stale references to deleted/moved planning files
- `majorTODO.md` and any active todo surface remain coherent

---

## Phase 5 — Delete/Archive Pass

Status: `complete`

Goal:

Remove or archive files that the manifest has confirmed are stale.

Deletion criteria:

- no imports
- no tests reference it
- no docs reference it
- no scripts invoke it
- not an app data file
- not needed for current manual workflow
- user has not marked it as retained

Validation:

- grep for deleted filenames
- run targeted tests/import checks
- update manifest or this file with final disposition

---

## Phase 6 — Final Verification and Remove Cleanup Plan

Status: `not started`

Goal:

Confirm cleanup is complete and remove this temporary plan.

Required checks:

- no `unknown` classifications remain
- root layout matches intended end state
- script README exists and reflects reality
- root README references only supported setup/run workflows
- no stale install/setup instructions remain
- targeted tests pass
- any full cheap validation suite passes if practical

Final action:

- delete `cleanupplan.md`

---

## Running Log

Add each cleanup pass below.

### Pass 4 — Non-Installer Script Organization

Status: `complete`

Scope:

- Organized remaining non-installer utilities under `scripts/validation/`, `scripts/migration/`, `scripts/build/`, and `scripts/audit/`.
- Left `scripts/quick-install.sh` in place as the supported checkout installer.
- Left `scripts/launch-windows.bat` in place because it is a direct launcher and the requested grouping did not include launcher relocation.
- Updated `scripts/README.md`, README LAN smoke reference, the LAN inline script GitHub workflow, and the monster backfill test helper path.
- Updated `docs/repo_cleanup_manifest.md` to reflect the new script paths and remaining decisions.

Validation:

- `find scripts -maxdepth 4 -type f | sort`
- `grep -RIn "check-lan-script\|lan-smoke-playwright\|build_exe\|backfill\|audit\|scripts/" README.md docs scripts .github tests 2>/dev/null || true`
- `./.venv/bin/python -m py_compile $(find scripts -type f -name "*.py" | sort)`
- `bash -n scripts/quick-install.sh`
- `.github/workflows/lan-inline-script-check.yml` checked for old validation script paths.
- `./.venv/bin/python -m unittest tests.test_monster_backfill_pipeline`

Remaining user-decision items:

- None. `.claude/`, `.codex/`, and `claude-skills/` were resolved in cleanup pass 5.

Next recommended cleanup pass:

- Final generated-cache cleanup for untracked local artifacts such as `__pycache__/` and `.venv/`, followed by a final verification pass.

### Pass 5 — Local Agent Context Ignore Cleanup

Status: `complete`

Scope:

- Applied user decision that `.claude/`, `.codex/`, and `claude-skills/` are local development/agent context directories, not GitHub-tracked repo content.
- Added grouped `.gitignore` entries for `.claude/`, `.codex/`, and `claude-skills/`.
- Removed tracked `claude-skills/` files from the Git index only with `git rm --cached -r claude-skills`.
- Preserved `.claude/`, `.codex/`, and `claude-skills/` on disk.
- Updated `docs/repo_cleanup_manifest.md` dispositions so these are no longer `unknown` user-decision items.

Validation:

- `git status --short`
- `git ls-files .claude .codex claude-skills`
- `git check-ignore -v .claude/ .codex/ claude-skills/ || true`
- `test -d .claude && test -d .codex && test -d claude-skills`
- `git diff -- .gitignore cleanupplan.md docs/repo_cleanup_manifest.md`
- `grep -RIn ".claude\|.codex\|claude-skills" README.md docs scripts .github cleanupplan.md 2>/dev/null || true`

Remaining user-decision items:

- None.

Next recommended cleanup pass:

- Generated local artifact cleanup: remove untracked caches/environments such as `__pycache__/` and `.venv/` after confirming they remain ignored and reproducible.

### Pass 6 — Generated Local Artifact Cleanup

Status: `complete`

Scope:

- Confirmed no generated artifacts in the requested set were tracked by Git.
- Added/confirmed `.gitignore` coverage for Python bytecode, `.venv/`, `venv/`, pytest/mypy/ruff caches, coverage output, `htmlcov/`, build outputs, and local agent context.
- Removed non-`.venv` generated cache directories from the working tree:
  - `./__pycache__`
  - `./scripts/audit/__pycache__`
  - `./scripts/build/__pycache__`
  - `./scripts/migration/__pycache__`
  - `./scripts/validation/__pycache__`
  - `./tests/__pycache__`
- Preserved `.venv/` on disk because it is ignored, untracked, and still useful for local validation.
- Updated `docs/repo_cleanup_manifest.md` to reflect generated-artifact cleanup disposition.

Validation:

- `git status --short`
- `git ls-files "__pycache__" "*/__pycache__" ".venv" ".pytest_cache" ".mypy_cache" ".ruff_cache" ".coverage" "htmlcov"`
- `git check-ignore -v __pycache__/ .venv/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ || true`
- `find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name "htmlcov" \) -print | sort`
- `git diff -- .gitignore cleanupplan.md docs/repo_cleanup_manifest.md`

Next recommended cleanup pass:

- Launcher/root hygiene: decide whether to move `launcher.py` under a script launcher subdirectory and update `scripts/build/build_exe.py` plus docs in the same pass.

### Pass 7 — Launcher Root Hygiene

Status: `complete`

Decision:

- Moved `launcher.py` out of repo root to `scripts/launchers/launcher.py`.

Evidence:

- `launcher.py` is a Windows/desktop launcher wrapper, not the documented normal root entrypoint.
- README documents `dnd_initative_tracker.py`, `serve_headless.py`, and `scripts/quick-install.sh` as the normal entrypoints/workflow.
- The active source reference was the optional PyInstaller helper in `scripts/build/build_exe.py`.

Changes:

- Moved `launcher.py` to `scripts/launchers/launcher.py`.
- Updated the launcher wrapper so source execution resolves the repo root from `scripts/launchers/`.
- Updated `scripts/build/build_exe.py` to package `scripts/launchers/launcher.py`.
- Updated `scripts/README.md` and `docs/WINDOWS_EXECUTABLE.md` for the new launcher/build path.
- Updated `docs/repo_cleanup_manifest.md` counts and launcher disposition.

Validation:

- `./.venv/bin/python -m py_compile scripts/launchers/launcher.py scripts/build/build_exe.py`
- Manually inspected `scripts/launch-windows.bat`; it launches `dnd_initative_tracker.py` directly and does not reference `launcher.py`, so no path change was needed.
- `grep -RIn "launcher.py\|launch-windows.bat\|build_exe.py" README.md docs scripts .github tests cleanupplan.md docs/repo_cleanup_manifest.md 2>/dev/null || true`
- `git diff --stat`
- `git diff -- cleanupplan.md docs/repo_cleanup_manifest.md README.md docs scripts launcher.py`

Next recommended cleanup pass:

- Final cleanup verification: confirm no `unknown` manifest entries remain, root layout is intentional, script/docs references are current, then remove temporary `cleanupplan.md` if the cleanup workstream is accepted.

### Pass 0 — Plan Created

Status: `complete`

Changes:

- Created temporary cleanup plan.
- No repo files moved or deleted yet.

Next pass:

- Phase 1 audit manifest.

### Pass 1 — Phase 1 Cleanup Manifest

Status: `complete`

Changes:

- Created `docs/repo_cleanup_manifest.md`.
- Classified every root-level entry found by `find . -maxdepth 1 -mindepth 1`.
- Classified every script-like file under `scripts/`.
- Recorded questionable docs/planning/maintenance files discovered under root, `docs/`, `scripts/`, and `.github/`.
- No files were moved, deleted, renamed, or rewritten outside this audit manifest and this cleanup plan update.

Key findings:

- Root cleanup has clear generated-artifact delete candidates: `.venv/`, root `__pycache__/`, and nested Python cache directories in a later generated-artifact pass.
- `launcher.py` was the clearest root move candidate; it was moved to `scripts/launchers/launcher.py` in cleanup pass 7 after updating the build helper and docs.
- Active validation scripts (`scripts/check-lan-script.mjs`, `scripts/lan-smoke-playwright.py`) are good candidates for `scripts/validation/`, but `.github/workflows/lan-inline-script-check.yml` must move with them.
- Legacy install/update/uninstall scripts should not be moved until README, `scripts/README.md`, `update_checker.py`, registered uninstall paths, and published one-line install URLs are checked together.
- `.claude/`, `.codex/`, and `claude-skills/` needed user decision before cleanup disposition; resolved in cleanup pass 5 as local-only ignored context.

Next pass:

- Phase 2 root hygiene: generated artifacts and launcher root clutter have been handled; proceed to final verification.

### Pass 2 — Planning Docs and Installer Classification Cleanup

Status: `complete`

Changes:

- Removed inactive root `todo.md` after user decision that it is no longer active root planning.
- Moved inactive `docs/player-yaml-spellcasting-report.md` to `docs/archive/player-yaml-spellcasting-report.md`.
- Removed stale `todo.md` references from `majorTODO.md` and `.github/instructions/docs-tracker.instructions.md`.
- Confirmed `scripts/quick-install.sh` is the current live installer path documented by `README.md`.
- Narrowed `README.md` and `scripts/README.md` wording so legacy install/update/uninstall scripts are not presented as the current source-checkout install path.
- Updated `docs/repo_cleanup_manifest.md` to reflect the removed/archived planning files and to mark legacy install/update/uninstall scripts as `delete-candidate` while preserving `scripts/quick-install.sh`.

Validation:

- Confirmed no remaining `todo.md` or `player-yaml-spellcasting-report` references outside the cleanup manifest/archive path.
- Confirmed `README.md` still points at `bash scripts/quick-install.sh` as the live installer.
- Confirmed no gameplay/runtime/data files were edited.

Remaining user-decision items:

- None. `.claude/`, `.codex/`, and `claude-skills/` were resolved in cleanup pass 5.

Next pass:

- Dedicated legacy installer cleanup: decide delete vs archive for old platform install/update/uninstall scripts, update or remove `update_checker.py` managed-install updater references with focused tests, and keep `scripts/quick-install.sh` stable.

### Pass 3 — Legacy Installer/Updater Cleanup

Status: `complete`

Changes:

- Confirmed `scripts/quick-install.sh` remains the current live source-checkout installer and kept it unmoved/unchanged.
- Deleted obsolete legacy install/update/uninstall scripts:
  - `scripts/install-linux.sh`
  - `scripts/install-windows.bat`
  - `scripts/install-windows.ps1`
  - `scripts/quick-install.ps1`
  - `scripts/uninstall-linux.sh`
  - `scripts/uninstall-windows.bat`
  - `scripts/uninstall-windows.ps1`
  - `scripts/update-linux.sh`
  - `scripts/update-windows.ps1`
- Retired `update_checker.py` managed updater script launching. `get_update_command()` now always returns `None`, so the app stays on the existing manual-instructions path.
- Updated `get_manual_update_instructions()` to document the supported source-checkout update path: `git fetch`, `git pull --ff-only`, then `bash scripts/quick-install.sh`.
- Updated `tests/test_update_checker.py` for the retired auto-launch path and live installer manual instructions.
- Updated `README.md` and `scripts/README.md` so they no longer present legacy install/update/uninstall scripts.
- Updated `docs/repo_cleanup_manifest.md` dispositions and script counts.

Validation:

- `./.venv/bin/python -m py_compile update_checker.py`
- `./.venv/bin/python -m unittest tests.test_update_checker`
- Confirmed `README.md` still documents `bash scripts/quick-install.sh`.
- Confirmed no remaining active references to deleted legacy script paths outside cleanup bookkeeping.

Remaining user-decision items:

- None. `.claude/`, `.codex/`, and `claude-skills/` were resolved in cleanup pass 5.

Next pass:

- Script utility organization: move non-live utility scripts into `scripts/validation/`, `scripts/migration/`, `scripts/build/`, or `scripts/audit/` with workflow/docs updates and focused syntax checks.

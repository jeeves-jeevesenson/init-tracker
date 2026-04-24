# Repo Cleanup Manifest

Cleanup classification manifest for the repo cleanup workstream.

Classification labels are from `cleanupplan.md`: `keep-root`, `move-to-scripts`, `move-to-docs`, `move-to-tests`, `archive`, `delete-candidate`, `unknown`.

## Audit Inputs

- `git status --short`
- `find . -maxdepth 1 -mindepth 1 -printf "%f\n" | sort`
- `find scripts -maxdepth 4 -type f | sort`
- `find docs -maxdepth 4 -type f | sort || true`
- `find .github -maxdepth 4 -type f | sort || true`
- `find . -maxdepth 3 -type f \( -name "*.sh" -o -name "*.ps1" -o -name "*.bat" -o -name "*.cmd" -o -name "*.py" \) | sort`
- `grep -RInE "helper_script|update_checker|launcher|serve_headless|install|setup|bootstrap|majorTODO|todo\.md|CLAUDE|AGENTS|cleanupplan" . --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.venv`
- `find . -name "*.py" -not -path "./.git/*" -not -path "./__pycache__/*" -not -path "./.venv/*" -print0 | xargs -0 grep -nE "subprocess|argparse|if __name__ == .__main__.|click|typer|fire"`

Note: `rg` was not installed in this environment, so `grep` fallbacks were used.

## Root-Level Inventory

| Current path | Classification | Proposed final path or disposition | Evidence/references found | Validation needed before move/delete | Risk/notes |
| --- | --- | --- | --- | --- | --- |
| `.claude/` | `delete-candidate` | Keep local on development machines, ignore with `.gitignore`, and exclude from tracked repo state. | User decision in cleanup pass 5: local-only agent context; root inventory includes `.claude/settings.local.json`. | `git ls-files .claude`; `git check-ignore -v .claude/`; confirm directory remains on disk. | Do not delete local directory; disposition is removal from GitHub-tracked repo only. |
| `.codex/` | `delete-candidate` | Keep local on development machines, ignore with `.gitignore`, and exclude from tracked repo state. | User decision in cleanup pass 5: local-only agent context; root inventory includes `.codex/config.toml`. | `git ls-files .codex`; `git check-ignore -v .codex/`; confirm directory remains on disk. | Do not delete local directory; disposition is removal from GitHub-tracked repo only. |
| `.git/` | `keep-root` | Keep at repo root. | Git repository metadata. | None. | Not a cleanup target. |
| `.github/` | `keep-root` | Keep `.github/`; optionally audit contents in a later maintenance-doc pass. | Contains workflows, Copilot instructions, repo skills, and instruction files. | If contents change, validate Actions/workflow references and instruction applicability. | Repo automation/config belongs under `.github/`. |
| `.gitignore` | `keep-root` | Keep at repo root. | Standard VCS config; cleanup pass 6 added standard generated-artifact ignores for Python/test/build caches. | Recheck `git check-ignore` when adding new generated artifact types. | Now covers local agent context, `.venv/`, `venv/`, Python bytecode, pytest/mypy/ruff caches, coverage output, and build artifacts. |
| `.venv/` | `delete-candidate` | Keep local environment on disk, ignore with `.gitignore`, and exclude from tracked repo state. | README and `scripts/quick-install.sh` create `.venv`; `git ls-files .venv` returned no tracked files in cleanup pass 6. | `git check-ignore -v .venv/`; confirm no tracked files under `.venv`. | Local environment, not repo content. Preserved in cleanup pass 6 per constraint/preference. |
| `AGENTS.md` | `keep-root` | Keep at repo root. | User-provided repo instructions; `.github/copilot-instructions.md` and `CLAUDE.md` mirror similar agent guidance. | None for cleanup. | Standing agent context. |
| `CLAUDE.md` | `keep-root` | Keep at repo root. | Standing Claude instructions; overlaps with `AGENTS.md`. | Later docs pass can decide whether duplication is intentional. | Keep until user decides whether both agent surfaces are needed. |
| `Items/` | `keep-root` | Keep at repo root. | App data directory; cleanupplan explicitly excludes `Items/` from initial cleanup. | None in this pass. | Out of scope. |
| `Monsters/` | `keep-root` | Keep at repo root. | App data directory; cleanupplan explicitly excludes `Monsters/` from initial cleanup. | None in this pass. | Out of scope. |
| `README.md` | `keep-root` | Keep at repo root. | Main user-facing docs; references `dnd_initative_tracker.py`, `serve_headless.py`, `helper_script.py`, `scripts/quick-install.sh`. | Later README pass should check references after any moves. | Current live installer remains `scripts/quick-install.sh`; legacy install/update/uninstall references removed. |
| `Spells/` | `keep-root` | Keep at repo root. | App data directory; cleanupplan explicitly excludes `Spells/` from initial cleanup. | None in this pass. | Out of scope. |
| `VERSION` | `keep-root` | Keep at repo root. | Top-level version file. | Search consumers before any move. | Likely release/runtime metadata. |
| `__pycache__/` | `delete-candidate` | Removed from working tree and ignored going forward. | Root inventory showed generated Python bytecode cache; `git ls-files` returned no tracked cache directories in cleanup pass 6. | `find . -path ./.venv -prune -o -type d -name "__pycache__" -print`; `git check-ignore -v __pycache__/`. | Non-`.venv` Python cache directories removed in cleanup pass 6. `.venv` internals were left intact. |
| `assets/` | `keep-root` | Keep at repo root. | README documents `assets/web/lan/`; scripts and app reference assets. | None for repo-structure cleanup. | Core app/web asset directory. |
| `character_autofill.py` | `keep-root` | Keep at repo root unless a later package-layout pass moves core modules together. | `tests/test_character_autofill.py` exists; discovered as Python module. | Run focused tests if moved. | Runtime/helper module, not simple script clutter. |
| `claude-skills/` | `delete-candidate` | Keep local on development machines, ignore with `.gitignore`, and remove tracked entries from the Git index only. | User decision in cleanup pass 5: local-only agent context; `git ls-files claude-skills` showed tracked skill files before index cleanup. | `git ls-files claude-skills`; `git check-ignore -v claude-skills/`; confirm directory remains on disk. | Removed from index with `git rm --cached -r claude-skills`; do not delete local directory. |
| `cleanupplan.md` | `keep-root` | Keep during cleanup workstream; delete in Phase 6 per its own plan. | User states it is temporary source of truth; cleanupplan final action says delete `cleanupplan.md`. | Before deletion, verify cleanup complete and no unknown classifications remain. | Active temporary tracker, not dead clutter yet. |
| `combat_service.py` | `keep-root` | Keep at repo root unless a future package-layout migration moves core modules. | `majorTODO.md` and docs identify `CombatService`; tests import/use it broadly. | Focused service tests if moved. | Core backend/service module. |
| `dnd_initative_tracker.py` | `keep-root` | Keep at repo root. | README calls it main entry script; AGENTS/CLAUDE guardrail says do not rename. | None for cleanup. | Historical typo intentionally preserved. |
| `docs/` | `keep-root` | Keep at repo root. | Cleanupplan deliverable lives in `docs/`; existing docs are under `docs/`. | Later docs pass may archive stale docs. | Proper documentation directory. |
| `helper_script.py` | `keep-root` | Keep at repo root for now. | README identifies it as core Tkinter UI/combat/map module; `dnd_initative_tracker.py` imports it from same folder; tests reference it. | Any move requires import/path compatibility checks and many focused tests. | Monolithic core module despite script-like name. |
| `majorTODO.md` | `keep-root` | Keep at repo root for now; later docs pass may decide whether active planning remains root or moves under docs. | File states it is durable planning source; AGENTS/CLAUDE require it as source of truth. | If moved, update agent instructions and grep references. | Active planning tracker. |
| `map_state.py` | `keep-root` | Keep at repo root unless core modules are packaged together later. | Tests reference map state behavior; app imports tactical/map model. | Focused map/session tests if moved. | Core runtime module. |
| `player_command_contracts.py` | `keep-root` | Keep at repo root unless core modules are packaged together later. | AGENTS migration pattern names this file; tests cover command contracts. | Run command-contract tests if moved. | Core backend contract module. |
| `player_command_service.py` | `keep-root` | Keep at repo root unless core modules are packaged together later. | AGENTS migration pattern names this file; command dispatch/service tests exist. | Run command service/allowlist tests if moved. | Core backend service module. |
| `players/` | `keep-root` | Keep at repo root. | App data directory; cleanupplan explicitly excludes `players/` from initial cleanup. | None in this pass. | Out of scope. |
| `presets/` | `keep-root` | Keep at repo root. | App data directory; cleanupplan explicitly excludes `presets/` from initial cleanup. | None in this pass. | Out of scope. |
| `requirements.txt` | `keep-root` | Keep at repo root. | README and installers reference it; CI/setup installs from it. | None unless dependency workflow changes. | Standard Python dependency manifest. |
| `scripts/` | `keep-root` | Keep at repo root; organize subdirectories in Phase 3. | README and `scripts/README.md` document install/update/smoke scripts. | After reorganization, grep README/docs/workflows for stale paths. | Script directory is intentional; contents need organization. |
| `serve_headless.py` | `keep-root` | Keep at repo root as current headless entrypoint. | README and `majorTODO.md` identify it as headless/browser-first host; tests cover headless host. | Do not move unless entrypoint/docs/tests are updated. | Current supported runtime entrypoint. |
| `ship_blueprints.py` | `keep-root` | Keep at repo root unless core modules are packaged together later. | `scripts/migration/import_tiled_ship_blueprints.py` imports it; ship tests exist. | Run ship blueprint/composite tests if moved. | Core helper module for ship assets/gameplay. |
| `tests/` | `keep-root` | Keep at repo root. | Standard test suite directory. | None for cleanup. | `tests/__pycache__/` was removed as generated local artifact in cleanup pass 6. |
| `tk_compat.py` | `keep-root` | Keep at repo root unless core modules are packaged together later. | `majorTODO.md` identifies `INIT_TRACKER_HEADLESS`/`HeadlessRoot`; headless tests cover it. | Run headless tests if moved. | Core compatibility module. |
| `update_checker.py` | `keep-root` | Keep at repo root. | `dnd_initative_tracker.py` imports it; `tests/test_update_checker.py` covers it. | Run update checker/startup update tests if edited. | Managed updater script launch path was removed in cleanup pass 3; update prompts now use manual `bash scripts/quick-install.sh` instructions. |

## Script-Like Files Under `scripts/`

| Current path | Classification | Proposed final path or disposition | Evidence/references found | Validation needed before move/delete | Risk/notes |
| --- | --- | --- | --- | --- | --- |
| `scripts/audit/spell_automation_audit.py` | `move-to-scripts` | Keep at `scripts/audit/spell_automation_audit.py`. | Generates/references `Spells/automation_audit_level_0_6.md`; script-like `__main__`; `scripts/README.md` documents it. | Py compile; confirm generated audit report state before running. | Audit utility, not normal runtime. Moved in cleanup pass 4. |
| `scripts/build/build_exe.py` | `move-to-scripts` | Keep at `scripts/build/build_exe.py`. | `scripts/README.md` documents optional PyInstaller build; now packages `scripts/launchers/launcher.py`. | Py compile; validate launcher path after any launcher move. | Build helper path updated in cleanup pass 7. |
| `scripts/build/create_icon.py` | `move-to-scripts` | Keep at `scripts/build/create_icon.py`. | `scripts/README.md` documents it; `scripts/build/build_exe.py` prompts for this path when icon is missing. | Py compile; verify generated icon path if edited. | Generates `assets/icon.ico`. Moved in cleanup pass 4. |
| `scripts/launch-windows.bat` | `move-to-scripts` | Keep at `scripts/launch-windows.bat` for now. | `scripts/README.md` documents direct Windows repo launcher. | Manual Windows path validation before any launcher move. | Left top-level in `scripts/` because this pass did not include launcher relocation. |
| `scripts/launchers/launcher.py` | `move-to-scripts` | Keep at `scripts/launchers/launcher.py`. | Primarily used by optional PyInstaller build; `scripts/build/build_exe.py` now packages this path; `scripts/README.md` documents it. | Py compile with `scripts/build/build_exe.py`; verify build helper path if launcher moves again. | Moved from repo root in cleanup pass 7; direct script execution resolves the repo root from `scripts/launchers/`. |
| `scripts/migration/aidedd_image_archive.py` | `move-to-scripts` | Keep at `scripts/migration/aidedd_image_archive.py`. | Has argparse CLI and network downloader docstring; test `tests/test_aidedd_monster_images.py` exists. | Py compile; dry-run/syntax check; confirm content/licensing workflow before reuse. | External image archival may be historical or sensitive; grouped as migration/data utility in cleanup pass 4. |
| `scripts/migration/backfill_monster_sections.py` | `move-to-scripts` | Keep at `scripts/migration/backfill_monster_sections.py`. | Argparse CLI; `tests/test_monster_backfill_pipeline.py` loads this path. | Py compile; focused monster backfill tests; confirm external fetch behavior before running. | Migration/data backfill script, not normal user workflow. Moved in cleanup pass 4. |
| `scripts/migration/build_shop_catalog.py` | `move-to-scripts` | Keep at `scripts/migration/build_shop_catalog.py`. | Argparse CLI; shop catalog tests exist; script writes `Items/Shop/catalog.yaml`; usage string updated. | Py compile; run shop catalog loader/write tests before behavior changes. | Touches item data if executed; do not run casually. Moved in cleanup pass 4. |
| `scripts/migration/import_srd_items.py` | `move-to-scripts` | Keep at `scripts/migration/import_srd_items.py`. | Argparse CLI; imports external SRD item data; help examples updated. | Py compile; dry-run where supported; confirm no generated item churn. | Data-writing script; cleanup must not touch `Items/` in this phase. Moved in cleanup pass 4. |
| `scripts/migration/import_tiled_ship_blueprints.py` | `move-to-scripts` | Keep at `scripts/migration/import_tiled_ship_blueprints.py`. | Argparse CLI; imports `ship_blueprints`; ship blueprint tests exist. | Py compile; run ship blueprint tests if behavior changes. | Writes generated blueprint assets when executed. Moved in cleanup pass 4. |
| `scripts/quick-install.sh` | `move-to-scripts` | Keep stable at `scripts/quick-install.sh`. | README documents it as the current source-checkout installer. | Shell syntax check and `--dry-run` after edits. | Current live installer path. Do not move while README points here. |
| `scripts/validation/check-lan-script.mjs` | `move-to-scripts` | Keep at `scripts/validation/check-lan-script.mjs`. | `scripts/README.md` documents it; `.github/workflows/lan-inline-script-check.yml` runs it. | Run workflow or Node syntax validation when changed. | Active CI validation; workflow updated in cleanup pass 4. |
| `scripts/validation/lan-smoke-playwright.py` | `move-to-scripts` | Keep at `scripts/validation/lan-smoke-playwright.py`. | `scripts/README.md`, README, and `.github/workflows/lan-inline-script-check.yml` reference it. | Py compile; run smoke only when Playwright deps/browser are available. | Active CI validation; workflow and README updated in cleanup pass 4. |

## Questionable Docs, Planning, And Maintenance Files

| Current path | Classification | Proposed final path or disposition | Evidence/references found | Validation needed before move/delete | Risk/notes |
| --- | --- | --- | --- | --- | --- |
| `cleanupplan.md` | `keep-root` | Keep until cleanup Phase 6, then delete. | Temporary source of truth for cleanup workstream. | Verify final cleanup criteria before deletion. | Active temporary file. |
| `majorTODO.md` | `keep-root` | Keep root unless later user decision moves planning into docs. | Declares itself durable planning source; agent instructions require it. | Update all references if moved. | High-value active tracker. |
| `AGENTS.md` | `keep-root` | Keep root. | Standing Codex/autonomous-agent context. | None. | User-facing agent control file. |
| `CLAUDE.md` | `keep-root` | Keep root or consolidate only after user decision. | Standing Claude context; duplicates much of `AGENTS.md`. | Confirm whether Claude-specific file is still needed. | Duplication is intentional until proven otherwise. |
| `docs/WINDOWS_EXECUTABLE.md` | `move-to-docs` | Keep under docs for now; later decide active docs vs `docs/archive/WINDOWS_EXECUTABLE.md`. | Optional PyInstaller doc; now points regular users to root `README.md` and `scripts/quick-install.sh`. | Check against current build scripts and installer state before archiving. | Optional advanced build doc, not the primary install path. |
| `docs/dm-web-migration.md` | `move-to-docs` | Keep under docs for now; possible archive after migration boundary is superseded. | Documents DM web/backend migration boundary; references current routes and `serve_headless.py`. | Verify route/test references before archiving. | Historical plus architectural reference. |
| `docs/archive/player-yaml-spellcasting-report.md` | `archive` | Retain in `docs/archive/`. | User confirmed it is not active; content is a point-in-time spellcasting pipeline audit. | None unless archive docs are later pruned. | Archived in cleanup pass 2. |
| `docs/shop_inventory_design.md` | `move-to-docs` | Keep under docs as active design contract until superseded. | States it freezes shop/inventory data model; shop/inventory tests and code exist. | Validate current implementation before archiving. | Active design reference. |
| `scripts/README.md` | `move-to-docs` | Keep as `scripts/README.md`; update during scripts organization. | Documents current checkout installer, launchers, utilities, and validation scripts. | Update after any script path move. | Belongs with scripts even though it is documentation. |
| `.github/copilot-instructions.md` | `keep-root` | Keep under `.github/`. | Agent guidance references `majorTODO.md` and migration workflow. | None unless agent docs are consolidated. | Repo automation/instruction metadata. |
| `.github/instructions/docs-tracker.instructions.md` | `keep-root` | Keep under `.github/instructions/`. | Applies to `majorTODO.md` and `docs/**/*.md`. | Update if planning files move again. | `todo.md` reference removed in cleanup pass 2. |
| `.github/instructions/lan-web.instructions.md` | `keep-root` | Keep under `.github/instructions/`. | Applies to `assets/web/**`. | None for cleanup. | Maintenance instruction file. |
| `.github/instructions/python-core.instructions.md` | `keep-root` | Keep under `.github/instructions/`. | Applies to `**/*.py`. | None for cleanup. | Maintenance instruction file. |
| `.github/instructions/python-hybrid.instructions.md` | `keep-root` | Keep under `.github/instructions/`. | Applies to `**/*.py`. | None for cleanup. | Potential overlap with python-core, but not a Phase 1 action. |
| `.github/instructions/scripts.instructions.md` | `keep-root` | Keep under `.github/instructions/`; update apply paths if scripts are reorganized. | Applies to `scripts/**`; contains install/update safety rules. | Update if script paths move outside `scripts/**`. | Active maintenance instruction. |
| `.github/instructions/yaml-data.instructions.md` | `keep-root` | Keep under `.github/instructions/`. | Applies to YAML data directories excluded from cleanup. | None for cleanup. | Active guardrail. |
| `.github/skills/backend-family-extraction/SKILL.md` | `keep-root` | Keep under `.github/skills/`. | Skill for backend/player-command migration; references `majorTODO.md`. | None for repo cleanup. | Active agent workflow metadata. |
| `.github/workflows/copilot-setup-steps.yml` | `keep-root` | Keep under `.github/workflows/`. | GitHub Actions workflow for Copilot setup. | Validate workflow only if edited. | CI/automation config. |
| `.github/workflows/lan-inline-script-check.yml` | `keep-root` | Keep under `.github/workflows/`; update if validation script paths move. | Runs `node scripts/validation/check-lan-script.mjs` and `python scripts/validation/lan-smoke-playwright.py`. | Validate workflow after script reorganization. | Active CI path coupling; updated in cleanup pass 4. |

## High-Confidence Candidates

Highest-confidence move candidates for a later pass:

- None after cleanup pass 7.

Highest-confidence delete candidates for a later pass:

- `.venv/` local generated environment remains ignored and untracked, but was intentionally preserved on disk in cleanup pass 6.

Unknown/risky files needing user decision:

- None after cleanup pass 5.
## Completed Cleanup Actions

- `todo.md` was removed in cleanup pass 2 after user decision that it is no longer active root planning. Its stale references were removed from `majorTODO.md` and `.github/instructions/docs-tracker.instructions.md`.
- `docs/player-yaml-spellcasting-report.md` was moved to `docs/archive/player-yaml-spellcasting-report.md` in cleanup pass 2.
- Legacy install/update/uninstall scripts were deleted in cleanup pass 3: `scripts/install-linux.sh`, `scripts/install-windows.bat`, `scripts/install-windows.ps1`, `scripts/quick-install.ps1`, `scripts/uninstall-linux.sh`, `scripts/uninstall-windows.bat`, `scripts/uninstall-windows.ps1`, `scripts/update-linux.sh`, and `scripts/update-windows.ps1`.
- `update_checker.py` managed updater script launch support was retired in cleanup pass 3; manual update instructions now point to `bash scripts/quick-install.sh`.
- Non-installer utility scripts were organized in cleanup pass 4:
  - validation scripts moved to `scripts/validation/`
  - data/import/backfill utilities moved to `scripts/migration/`
  - build helpers moved to `scripts/build/`
  - spell automation audit moved to `scripts/audit/`
  - `.github/workflows/lan-inline-script-check.yml`, README, `scripts/README.md`, and `tests/test_monster_backfill_pipeline.py` were updated for the new paths.
- Local agent/developer context directories were made local-only in cleanup pass 5: `.claude/`, `.codex/`, and `claude-skills/` are ignored by `.gitignore`; tracked `claude-skills/` entries were removed from the Git index only.
- Generated local artifacts were cleaned in cleanup pass 6: non-`.venv` `__pycache__/` directories were removed from the working tree, no generated artifacts in the requested set were tracked, `.venv/` was preserved on disk, and `.gitignore` now covers standard Python/test coverage caches.
- Root launcher clutter was cleaned in cleanup pass 7: `launcher.py` moved to `scripts/launchers/launcher.py`; `scripts/build/build_exe.py`, `scripts/README.md`, and `docs/WINDOWS_EXECUTABLE.md` were updated.

## Audit Counts

- Root-level entries classified: 34
- Script-like files under `scripts/` classified: 13

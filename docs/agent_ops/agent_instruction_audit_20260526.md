# Agent Instruction Audit - 2026-05-26

## Scope

This audit covers the repo-owned agent instruction corpus used by Gemini,
Codex, ChatGPT, Copilot, and the local AGY/Antigravity workflow. It is a
Gate A0 artifact only: no application logic, tests, YAML data, production
configuration, deployment topology, or runtime behavior changed.

Required recon commands were run:

```bash
git status --short
git log --oneline --decorate -10
find . -maxdepth 3 \( -name 'GEMINI.md' -o -name 'AGENTS.md' -o -name 'CLAUDE.md' -o -name '*copilot*' -o -name '*.instructions.md' \) -print | sort
find .gemini -maxdepth 5 -type f -print | sort 2>/dev/null || true
find .agent -maxdepth 6 -type f -print | sort 2>/dev/null || true
find scripts/agy scripts -maxdepth 3 -type f \( -name '*agent*' -o -name '*agy*' -o -name '*validate*' -o -name '*preflight*' \) -print 2>/dev/null | sort
find docs -maxdepth 4 -type f \( -path '*ai-workflows*' -o -path '*agent*' -o -name '*gemini*' -o -name '*workflow*' \) -print | sort
find .gemini/commands -type f -name '*.toml' -print 2>/dev/null | sort
```

Current repo state at audit start:

- `main` was at `993a8b6 Harden production recovery operating plan`.
- `git status --short` showed only pre-existing untracked `docs/runtime_reports/wip_diffs/`.
- `.gemini/commands/init/` existed.
- `.gemini/commands/recovery/` did not exist.

## Controlling Recovery Truth

For normal platform migration, current code and `majorTODO.md` remain the
durable planning source. For active production recovery, the gate plan in
`docs/production_recovery_living_doc_20260526.md` controls when it differs
from older trackers or docs.

This precedence is now explicit in `GEMINI.md` and was mirrored at the
top level in `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md`
during A0.1.

## Instruction Source Inventory

| Source | Applies To | What It Tells Agents | Conflicts / Overlaps | Stale or Superseded Claims | Recommended Action |
| --- | --- | --- | --- | --- | --- |
| `GEMINI.md` | Gemini, all agents by reference | Mission, source-of-truth, measured debugging, architecture direction, validation, browser JS syntax check, AGY links. | Overlaps with `AGENTS.md`, `CLAUDE.md`, Copilot root instructions. Previously omitted recovery precedence and `dmcontrol` JS checks. | Old source-of-truth language said code + `majorTODO.md` without recovery gate override. JS check listed only `dm` and `lan`. | Updated in A0. Keep as Gemini root and recovery entry point. |
| `AGENTS.md` | Codex and autonomous coding agents | Migration mission, backend extraction pattern, scope discipline, validation/reporting, no commit/push, JS syntax check for browser assets. | Same durable tracker language as older roots; detailed older browser section still focuses on `dm` and `lan`, but the A0.1 top recovery section adds `dmcontrol`. | Predates recovery operating plan below the new top section. | Updated in A0.1 with top-level recovery precedence, no gate mixing, no production/commit/push actions, and `dmcontrol` JS/smoke rule. |
| `CLAUDE.md` | Claude | Same migration mission and player-command extraction workflow as `AGENTS.md`, plus A0.1 recovery precedence. | No detailed browser JS syntax section, but the A0.1 top recovery section adds recovery browser readiness and `dmcontrol` syntax requirements. | Predates recovery plan below the new top section. | Updated in A0.1 with top-level recovery precedence, no gate mixing, no production/commit/push actions, and `dmcontrol` JS/smoke rule. |
| `.github/copilot-instructions.md` | Copilot | Same migration mission and extraction workflow; no commit/push; no desktop-first target; plus A0.1 recovery precedence. | No detailed browser JS syntax section, but the A0.1 top recovery section adds recovery browser readiness and `dmcontrol` syntax requirements. | Predates recovery plan below the new top section. | Updated in A0.1 with top-level recovery precedence, no gate mixing, no production/commit/push actions, and `dmcontrol` JS/smoke rule. |
| `.github/instructions/docs-tracker.instructions.md` | Copilot on `majorTODO.md`, docs | Keep repo reality ahead of aspiration; keep `majorTODO.md` primary migration tracker. | Conflicts by omission with recovery living doc precedence for active recovery. | "Primary migration tracker" is true for platform work, not recovery gate ordering. | Keep with qualifier in a later pass if needed. |
| `.github/instructions/lan-web.instructions.md` | Copilot on `assets/web/**` | Protocol stability, mobile-first UX, lightweight client, execute implementation-ready work, focused validation. | Lacks mandatory JS syntax check and browser smoke language. | Not stale, incomplete for recovery. | Keep; consider adding browser-asset syntax rule later. |
| `.github/instructions/python-core.instructions.md` | Copilot on Python | UI thread safety, LAN off UI thread, combat state source of truth, focused validation, YAML compatibility. | Broad implementation guidance can conflict with recovery allowed-file gates if not scoped. | Not stale, but no recovery gate precedence. | Keep. |
| `.github/instructions/python-hybrid.instructions.md` | Copilot on Python | Prefer backend authority, service seams, canonical prompt state, avoid new direct-mutation fallbacks. | Same mission as roots. | Not stale. | Keep. |
| `.github/instructions/scripts.instructions.md` | Copilot on `scripts/**` | Scripts should be rerunnable, safe, clear, portable. | Compatible with A0 scripts. | Not stale. | Keep. |
| `.github/instructions/yaml-data.instructions.md` | Copilot on YAML data | Avoid YAML churn, follow READMEs, no copyrighted non-SRD content. | Compatible. | Not stale. | Keep. |
| `.github/skills/backend-family-extraction/SKILL.md` | Copilot / GitHub skill users | Bounded player-command family extraction from `_lan_apply_action()` into `PlayerCommandService` and contracts. | Uses `majorTODO.md` as tracker; no recovery gate precedence. | Not stale for extraction work, not active recovery. | Keep as non-recovery migration skill. |
| `.github/workflows/copilot-setup-steps.yml` | Copilot setup workflow | CI-like setup for Copilot environment; no blanket dependency install. | Not an instruction source, but discovered by recon because name contains `copilot`. | Not stale. | Keep; no A0 action. |
| `.gemini/agents/docs-tracker-maintainer.md` | Gemini subagent | Reconcile `majorTODO.md` and docs with code/tests, preserve decision history. | Treats `majorTODO.md` as durable tracker; should not override recovery living doc during recovery. | Predates recovery plan. | Keep. Add recovery note later if docs-tracker subagent is used for recovery docs. |
| `.gemini/agents/init-tracker-architect.md` | Gemini subagent | Architecture mapping and next bounded migration slice; no edits. | Broad architecture guidance can conflict with recovery gate file limits unless explicitly bounded. | Not stale for migration analysis. | Keep. Recovery commands should be used instead for gate work. |
| `.gemini/agents/lan-contract-specialist.md` | Gemini subagent | LAN contracts, player-command service extraction, additive protocol changes. | Not a recovery gate command; can overlap Gate 2 spell/capability work if misused. | Not stale. | Keep for non-recovery contract reviews. |
| `.gemini/agents/measured-debugger.md` | Gemini subagent | No bug/perf fixes without evidence; use existing instrumentation. | Compatible with recovery, especially Gate 3. | Not stale. | Keep. |
| `.gemini/agents/runtime-observer.md` | Gemini subagent | Observe live runtime, launch/monitor server, classify findings, do not edit code. | It allows launching server and suggests LAN browser coordination; recovery A0 forbids production SSH/deploy, not local observation. | Contains hardcoded example LAN IP pattern; agents should confirm current address instead of guessing. | Keep but use cautiously; do not use for recovery implementation without explicit runtime observation task. |
| `.gemini/agents/spellbook-specialist.md` | Gemini subagent | Spellbook contract, class-aware spell model, LAN Manage Spells correction. | Overlaps Gate 2, but Gate 2 allowed files and validation must control. | Not stale. | Keep; recovery Gate 2 command should supersede for production recovery. |
| `.gemini/agents/tk-removal-investigator.md` | Gemini subagent | Inventory Tk dependencies and sequence removal; analysis only. | Not relevant to recovery gates unless explicitly scoped. | Not stale. | Keep. |
| `.gemini/commands/init/bug-pass.toml` | Gemini command | Evidence-first bug pass; no YAML; no refactor; no fixed claim without evidence. | Uses `majorTODO.md` and older measured-debugging reference; no recovery gate awareness. | Predates recovery plan. | Keep for non-gate bugs. Prefer recovery commands for gates. |
| `.gemini/commands/init/handoff-report.toml` | Gemini command | Self-contained handoff to Claude/Codex with findings, validation, next pass, `majorTODO.md` impact. | Handoff format useful, but recovery reports need smoke and git status. | Incomplete for recovery. | Keep; recovery `final_report` supersedes for gates. |
| `.gemini/commands/init/lan-contract-review.toml` | Gemini command | LAN/player-command contract review and bounded extraction proposal. | Not recovery-gated; could broaden beyond active gate. | Not stale, but not recovery entry. | Keep. |
| `.gemini/commands/init/lan-live-debug.toml` | Gemini command | Runtime observer: check port, launch server, give LAN URL, monitor logs. | Hardcoded example IP and local server launch may be inappropriate outside explicit observation. | Not stale, but risky for recovery if treated as implementation. | Keep. Use only when user explicitly asks for runtime observation. |
| `.gemini/commands/init/perf-observe.toml` | Gemini command | Observe performance using `LAN_PERF_DEBUG`, no edits. | Useful for Gate 3 evidence, but not a gate implementation command. | Not stale. | Keep; recovery Gate 3 command should control implementation. |
| `.gemini/commands/init/perf-pass.toml` | Gemini command | Hot-path investigation; one path, instrument first, no speculative optimization. | Uses `majorTODO.md` latency sections, not recovery gate order. | Predates recovery Gate 3 criteria. | Keep; recovery Gate 3 command supersedes during production recovery. |
| `.gemini/commands/init/repo-map.toml` | Gemini command | Architecture snapshot, no edits. | Broad analysis can distract recovery if used instead of gate commands. | Not stale. | Keep. |
| `.gemini/commands/init/runtime-soak.toml` | Gemini command | Long-running live soak, no code edits, record findings. | Good observation workflow but not gate implementation; launches runtime if used. | Not stale. | Keep for explicit observation only. |
| `.gemini/commands/init/spellbook-review.toml` | Gemini command | Spell-management contract review and corrective slice proposal. | Overlaps Gate 2 but lacks recovery allowed files/smoke criteria. | Not stale for review. | Keep; recovery Gate 2 command supersedes for gate implementation. |
| `.gemini/commands/init/tk-map.toml` | Gemini command | Tk/desktop dependency inventory, analysis only. | Not recovery-gate relevant. | Not stale. | Keep. |
| `.gemini/settings.example.json` | Gemini users | Loads `GEMINI.md`, respects gitignore, enables checkpointing, excludes risky shell commands. | Did not exclude `ssh`, `scp`, `rsync`, `systemctl`. | Incomplete for recovery no-production-access rule. | Updated in A0 with production-access command exclusions while keeping checkpointing enabled. |
| `.agent/rules/00-init-tracker-core.md` | AGY/Antigravity | Live-game safety, preflight, exact files/validation, no guessed FQDNs, no push/deploy/restart, warnings as stop. | Strong overlap with recovery guardrails. JS syntax check is generic and good. | References spell and `/dmcontrol` plans, not recovery doc. | Keep. Recovery docs should reuse its no-guess/no-production rules. |
| `.agent/rules/10-spell-engine-rules.md` | AGY spell work | Backend owns spell truth; fix primitives, not names; no silent paths; performance rules. | Gate 2 adjacent but not a recovery gate command. | Not stale. | Keep. |
| `.agent/rules/20-agent-safety-and-scope.md` | AGY spell work | Default spell-pass allowed files, ask-before list, never push/deploy/restart/secrets. | Conflicts with recovery gate file sets if applied blindly. | Not stale for spell passes; superseded by recovery gate allowed files during recovery. | Keep. |
| `.agent/workflows/00-preflight.md` | AGY | Run `scripts/agy/preflight.sh`, report branch, dirty files, commits, task, allowed files, validation. | Useful but not recovery-specific. | Not stale. | Keep; new recovery validation script fills gap. |
| `.agent/workflows/10-spell-pass-validate.md` | AGY | Run spell validation and task-specific tests; no warnings. | Spell-only; not recovery gate-wide. | Not stale. | Keep. |
| `.agent/workflows/20-audit-spell-primitives.md` | AGY | Run primitive purity audit. | Spell-only. | Not stale. | Keep. |
| `.agent/workflows/30-review-agent-output.md` | AGY | Run review script and block commit on warnings, output limit, outside allowed files. | Good review discipline; not recovery-gate-specific. | Not stale. | Keep. |
| `.agent/skills/init-tracker-spell-engine/SKILL.md` | AGY skill | Spell-engine workflow, preflight, allowed files, validation, runtime report, stop. | Gate 2 overlap, but recovery gate allowed files and living doc control. | Not stale for spell engine. | Keep; superseded by Gate 2 command for recovery. |
| `.agent/skills/init-tracker-spell-engine/references/spell-engine-guardrails.md` | AGY spell skill | Spell pass order and backend/frontend authority split. | Older pass order is historical relative to recovery Gates 1-6. | Superseded for production recovery ordering. | Keep as spell reference, not active recovery schedule. |
| `.agent/skills/init-tracker-spell-engine/scripts/audit_spell_pass.sh` | AGY skill wrapper | Execs `scripts/agy/audit_spell_primitives.sh`. | None. | Not stale. | Keep. |
| `.agent/skills/init-tracker-spell-engine/scripts/validate_spell_pass.sh` | AGY skill wrapper | Execs `scripts/agy/validate_spell_pass.sh`. | None. | Not stale. | Keep. |
| `scripts/agy/audit_spell_primitives.sh` | AGY / all agents | Grep-based spell primitive smell audit. | Spell-only. | Not stale. | Keep. |
| `scripts/agy/preflight.sh` | AGY / all agents | Print repo, branch/status, recent commits, diff stat, important docs. | Does not mention recovery doc. | Incomplete for recovery. | Keep; new `scripts/agent_context_bundle.sh` fills recovery handoff gap. |
| `scripts/agy/review_ready.sh` | AGY / all agents | Status, diff stat, spell validation, primitive audit, latest runtime reports. | Spell-only validation. | Not stale for spell passes. | Keep. |
| `scripts/agy/snapshot_agent_diff.sh` | AGY / all agents | Snapshot status/diff/stat to `/tmp`. | Compatible. | Not stale. | Keep. |
| `scripts/agy/validate_spell_pass.sh` | AGY / all agents | Compile core spell files, run warning-clean spell tests, optional pytest syntax test. | Uses `|| true` for some tests, so not strict enough as a recovery gate validator. | Not stale for exploratory spell passes, but insufficient for recovery pass/fail. | Keep; use new `scripts/agent_gate_validate.sh` for gates. |
| `docs/ai-workflows/gemini.md` | Gemini users, all agents by handoff | How to use Gemini, subagents, commands, runtime debugging, handoff, validation, never-do list. | References only `.gemini/commands/init/`; no recovery command set. Mentions Codex config values that may be outdated. | Predates recovery commands. | Keep. New `docs/agent_ops/gemini_recovery_workflow.md` supersedes for recovery. |
| `docs/ai-workflows/runtime-debugging.md` | Gemini runtime observation | How to launch Gemini YOLO for observation, runtime commands, logs, browser coordination, when to fix. | Says YOLO acceptable for observation; recovery implementation should not use YOLO. Contains example LAN IP. | Not stale if used for observation; unsafe if copied into recovery implementation. | Keep; recovery workflow qualifies YOLO use. |
| `docs/agent_tasks/templates/bounded_spell_pass.md` | AGY/agent prompt template | Bounded spell task template, validation, stop conditions, no deploy. | Spell-specific and older than recovery gate order. | Superseded for recovery gates. | Keep for non-recovery spell passes. |
| `docs/agent_tasks/templates/pass4_concentration_lifecycle.md` | AGY/agent prompt template | Implement spell pass 4 concentration lifecycle. | Historical pass template. | Work appears landed in `majorTODO.md`; not active recovery. | Archive later if template clutter becomes a problem. |
| `docs/agent_tasks/templates/pass5_summon_primitive.md` | AGY/agent prompt template | Implement summon primitive pass. | Historical pass template. | Work appears landed in `majorTODO.md`; not active recovery. | Archive later if template clutter becomes a problem. |
| `docs/agent_tasks/templates/pass6_dm_toolbox_long_rest.md` | AGY/agent prompt template | Implement DM Toolbox Long Rest. | Historical pass template; Gate 4 now owns resource/rest validation. | Work appears landed by older tracker, but recovery doc still requires Gate 4 validation. | Keep as historical template; recovery Gate 4 supersedes. |
| `docs/agent_rules/ANTIGRAVITY_INIT_TRACKER_GUIDE.md` | AGY/Antigravity | Plan mode, preflight, bounded task, validation, human review/commit, no push/deploy/restart. | No recovery gate commands. | Not stale, incomplete for recovery. | Keep. |
| `docs/production_recovery_living_doc_20260526.md` | All agents | Active production recovery definition, source/test/smoke matrix, map contract, gate order, allowed files, required tests, smoke, contradiction register. | Conflicts with older claims that map/headless are complete enough or production-ready. Gate 1 allowed-file list and "fix tests" line may need clarification when Gate 1 starts. | Current controlling recovery doc. | Keep as active recovery source of truth. |
| `docs/runtime_reports/production_recovery_docs_audit_20260526.md` | All agents | Gate 0C operational hardening summary and open contradictions. | Supports recovery doc; does not replace it. | Current as Gate 0C report. | Keep. |
| `docs/init_tracker_production_living_doc.md` | All agents, historical | Older production stabilization living doc. It already says it is superseded by the 2026-05-26 recovery doc. | May still contain valuable ADR/vocabulary, but not active gate plan. | Explicitly superseded for active recovery. | Keep archived. Do not use as gate source. |
| `docs/dm_control_surface_living_agent_plan.md` | Agents working `/dmcontrol` | Dedicated `/dmcontrol` design direction and update rules; no browser readiness without JS syntax for `dm`/`lan`. | Does not include `dmcontrol` in syntax check despite being a `/dmcontrol` plan. Older claims of landed `/dmcontrol` work conflict with recovery doc's "Contradicted" status. | Partly stale for recovery. | Keep as historical/design context; recovery Gate 1 controls active `/dmcontrol` work. Update later if `/dmcontrol` docs are in scope. |
| `majorTODO.md` | All agents | Durable platform tracker, migration direction, current milestone reality, stabilization and product passes, completed work logs. | Says `/dm` + `/dm/map` are "Complete enough" and includes hotfix claims, while recovery doc marks map surfaces contradicted and not production-ready without browser smoke. | Superseded by recovery doc only for active recovery gate plan. | Keep as platform tracker. Do not use it to skip recovery gates. |

The required recon command also printed `.git/worktrees/init-tracker-wt-next-player-resource-pass-copilot`, which is a git worktree metadata path, not a repo instruction source.

## Specific Contradictions and Resolutions

| Contradiction | Evidence | Resolution |
| --- | --- | --- |
| Durable tracker vs active recovery source | `GEMINI.md`, `AGENTS.md`, `CLAUDE.md`, and Copilot roots point to code + `majorTODO.md`; recovery work now has `docs/production_recovery_living_doc_20260526.md`. | `GEMINI.md` now states that the active recovery gate overrides `majorTODO.md` and older docs for recovery work. New workflow docs repeat this. |
| Browser JS syntax checks omit `dmcontrol` | A0 found `GEMINI.md`, `AGENTS.md`, and `docs/dm_control_surface_living_agent_plan.md` listing `assets/web/dm/index.html` and `assets/web/lan/index.html`; recovery gates require `assets/web/dmcontrol/index.html` checks when edited. | `GEMINI.md` and `scripts/agent_gate_validate.sh` include `assets/web/dmcontrol/index.html`. A0.1 added top-level recovery browser readiness and `dmcontrol` syntax rules to `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md`. `docs/dm_control_surface_living_agent_plan.md` remains historical/design context and should be synced only in a later scoped doc pass. |
| Gemini has init commands but no recovery gate commands | `.gemini/commands/init/*.toml` existed; `.gemini/commands/recovery/` did not. | A0 adds recovery commands for Gates 1-5, gate validation, and final reporting. |
| Old docs claim map/headless readiness while recovery doc says contradicted or not smoke-verified | `majorTODO.md` says `/dm` + `/dm/map` are complete enough; recovery doc marks DM Map and DM Control as "Contradicted" and production-ready only after browser smoke. | Recovery doc controls active gates. `majorTODO.md` remains historical/platform tracker and should not be used to skip Gate 1. |
| Old production living doc could be mistaken for active plan | `docs/init_tracker_production_living_doc.md` is still present and has detailed stabilization policy. | It already declares itself superseded. Audit records it as archived and not controlling. |
| Spell AGY workflow allows files that recovery Gate 2 forbids | `.agent/rules/20-agent-safety-and-scope.md` allows broad spell-pass files; Gate 2 limits recovery work to `monster_capability_service.py`, `spell_engine_primitives.py`, and `assets/web/lan/index.html`. | Recovery Gate 2 command should supersede AGY spell defaults for production recovery. |
| AGY spell validator is not a strict recovery validator | `scripts/agy/validate_spell_pass.sh` uses `|| true` on some focused tests. | A0 adds strict `scripts/agent_gate_validate.sh` for recovery gates. |
| Runtime observer workflows can imply local launch/browser work, but recovery implementation must not claim smoke from tests | Runtime observer docs/commands launch local server and coordinate browser testing; recovery doc requires browser smoke evidence. | Recovery workflow docs separate syntax/unit validation from user/manual browser smoke. No production SSH/deploy/restart without explicit request. |
| Gate 1 text had an internal scope tension | A0 found that Recovery Gate 1 allowed files omitted tests, but the required unit test line said to fix `tests/test_dm_tactical_map_routes.py`. | Resolved in A0.1: Gate 1 allowed files now explicitly include `tests/test_dm_tactical_map_routes.py`, the recovery living doc itself, and `docs/runtime_reports/gate1_map_surface_contract_*.md`; `/recovery:gate1_map_contract` now allows Gate 1 test-contract repair instead of telling agents to stop. |

## A0 Actions Taken

- Updated `GEMINI.md` with active recovery controls and `dmcontrol` browser syntax coverage.
- Updated `.gemini/settings.example.json` to keep checkpointing enabled and block common production-access commands (`ssh`, `scp`, `rsync`, `systemctl`) in the conservative example.
- Added recovery workflow docs under `docs/agent_ops/`.
- Added `.gemini/commands/recovery/` commands.
- Added strict recovery validation and context-bundle scripts.

## A0.1 Actions Taken

- Resolved the Gate 1 allowed-file/test-repair contradiction in `docs/production_recovery_living_doc_20260526.md`.
- Updated `/recovery:gate1_map_contract` to allow `tests/test_dm_tactical_map_routes.py` for Gate 1 test-contract repair.
- Mirrored the top-level recovery precedence, no gate mixing, no production action, and browser UI readiness rule into `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md`.

## Remaining Instruction Cleanup

- Consider archiving historical spell pass templates once recovery Gates 1-5 are complete.
- Consider adding a small note to `docs/dm_control_surface_living_agent_plan.md` that active recovery status comes from `docs/production_recovery_living_doc_20260526.md`.
- Consider a later broader Copilot sync for `.github/instructions/*.instructions.md`; A0.1 intentionally did not change those files.

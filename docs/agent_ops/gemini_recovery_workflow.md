# Gemini Recovery Workflow

Use this workflow for production recovery gates in `init-tracker`.
Use `docs/ai-workflows/gemini.md` for non-recovery analysis and older
`/init:*` commands.

## Start a Recovery Session

1. Start Gemini from the repo root:

   ```bash
   cd ~/src/init-tracker
   gemini
   ```

2. Confirm the repo context loaded from `GEMINI.md`.
3. Read the active recovery doc first:

   ```text
   @docs/production_recovery_living_doc_20260526.md
   ```

4. Pull in the current workflow context when useful:

   ```text
   @docs/agent_ops/gemini_recovery_workflow.md
   @docs/agent_ops/agent_instruction_audit_20260526.md
   ```

5. Run the command for exactly one active gate:

   ```text
   /recovery:gate1_map_contract
   /recovery:gate2_spell_capability
   /recovery:gate3_latency
   /recovery:gate4_resources_rest_pact
   /recovery:gate5_experimental_quarantine
   ```

Do not start Gate 1, Gate 2, or any later gate during an A0/docs-only task.

## Reload and List Commands

Gemini CLI discovers repo commands from `.gemini/commands/`.

- List available slash commands with the installed CLI's slash-command
  help/list UI, commonly `/help` or by typing `/` and reviewing completions.
- Recovery commands should appear under `/recovery:*`.
- Init commands remain under `/init:*`.
- If newly added command files do not appear, exit Gemini and restart it
  from the repo root so command discovery reloads from disk.

## Use `@file` Context

Use `@path` references to pin the current session to repo-owned truth:

```text
@GEMINI.md
@docs/production_recovery_living_doc_20260526.md
@docs/agent_ops/gemini_recovery_workflow.md
@docs/runtime_reports/production_recovery_docs_audit_20260526.md
```

For implementation gates, add only the files in the active gate's allowed
list plus the focused tests named in the recovery doc. Do not drag in broad
historical docs unless the gate explicitly needs them.

## Init Commands vs Recovery Commands

Use `/recovery:*` commands for production recovery gates.

Use `/init:*` commands only for non-gate work:

- `/init:repo-map` for broad architecture snapshots.
- `/init:bug-pass` for evidence-first bugs outside recovery gates.
- `/init:perf-pass` for non-gate latency investigation.
- `/init:spellbook-review` for non-gate spell-management review.
- `/init:handoff-report` for generic cross-agent handoff.

If an `/init:*` command conflicts with the active recovery doc, the recovery
doc wins.

## YOLO Policy

YOLO is forbidden for recovery implementation, production access, deploys,
service restarts, SSH, destructive cleanup, or broad edits.

YOLO is acceptable only for explicit observation sessions where:

- The user asked for runtime observation.
- The pass edits no files.
- The session is local/dev only.
- Gemini is using runtime-observer style evidence capture.
- The report clearly separates syntax/unit validation from manual browser
  smoke evidence.

Do not use YOLO to bypass gate scope.

## Gate Validation

Use the strict recovery validator after a gate implementation:

```bash
scripts/agent_gate_validate.sh gate1-map
scripts/agent_gate_validate.sh gate2-spells
scripts/agent_gate_validate.sh gate3-latency
scripts/agent_gate_validate.sh gate4-resources
scripts/agent_gate_validate.sh gate5-quarantine
```

The script:

- prints `git status --short`
- runs `git diff --check`
- compiles core Python files
- runs gate-specific unit tests from the recovery doc
- checks inline JavaScript with `node --check` if `assets/web/dm/index.html`,
  `assets/web/lan/index.html`, or `assets/web/dmcontrol/index.html` changed
- never starts production
- never commits or pushes

Manual browser smoke is still required for UI readiness claims. Record whether
smoke was performed by the user and what the user observed.

## Final Report Requirements

Every recovery gate report must include:

- Active gate name.
- Files inspected.
- Files changed.
- Commands/branches/components changed.
- Exact tests run and results.
- Exact JS syntax-check command and result if a browser HTML asset changed.
- Browser smoke status: performed/not performed, surface, result, and who ran it.
- Remaining risks and rough edges.
- Any scope escape or allowed-file tension.
- Whether `majorTODO.md` was updated or intentionally left alone.
- Single best next gate/pass.
- `git status --short`.

Do not commit, push, deploy, SSH, restart services, or change production
topology unless the user explicitly asks in the same task.

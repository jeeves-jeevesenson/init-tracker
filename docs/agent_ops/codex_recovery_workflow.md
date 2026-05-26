# Codex Recovery Workflow

Use Codex for bounded recovery implementation where cross-file reasoning,
careful validation, and strict scope control matter. Use this workflow for
Codex 5.5 Max or equivalent high-reasoning Codex sessions.

## When To Use Codex 5.5 Max

Use Codex for:

- Agent workflow, instruction, and validation-script repair.
- High-risk recovery gate implementation.
- Cross-file source/test contract repair.
- Backend-owned authority moves that require focused tests.
- Browser asset syntax fixes when the relevant HTML asset is explicitly
  allowed by the active gate.

## When Not To Use Codex

Do not spend Codex on:

- Cheap docs summarization that does not require repository edits.
- Broad grep-only audits with no implementation or decision pressure.
- Runtime smoke tests the user must do manually in a real browser.
- Production SSH/deploy/restart work unless explicitly requested.
- Mixing multiple recovery gates in one prompt.

## Required Codex Task Shape

Start each Codex recovery task with:

```text
Repo: ~/src/init-tracker
Active recovery doc: docs/production_recovery_living_doc_20260526.md
Gate: <exact gate name>
Allowed files:
- <exact paths>
Forbidden scope:
- no other gates
- no production SSH/deploy/restart
- no commit/push
- no app/test/YAML/config edits outside scope
Required validation:
- scripts/agent_gate_validate.sh <gate-id>
- any extra exact focused command
Manual smoke required:
- <surface and action from recovery doc>
```

If a task is docs/workflow-only, say that explicitly and list the only
allowed docs/scripts/config paths.

## Codex Operating Rules

- Read `docs/production_recovery_living_doc_20260526.md` before code changes.
- Treat the active gate in that doc as controlling when it differs from
  `majorTODO.md` or older docs.
- Inspect current repo state instead of relying on chat history.
- Make one broad, coherent, bounded pass.
- Do not start the next gate.
- Stop and report if the fix requires files outside the allowed list.
- Keep browser readiness claims separate from unit-test validation.
- Do not commit, push, deploy, SSH, restart services, edit secrets, change
  DNS/FQDNs/hostnames/ports, or alter production topology unless explicitly
  asked.

## Validation

Use the recovery validator:

```bash
scripts/agent_gate_validate.sh gate1-map
scripts/agent_gate_validate.sh gate2-spells
scripts/agent_gate_validate.sh gate3-latency
scripts/agent_gate_validate.sh gate4-resources
scripts/agent_gate_validate.sh gate5-quarantine
```

The script is safe for local validation only. It does not start production,
does not deploy, and does not commit or push.

For edited browser HTML assets, the validator extracts inline `<script>`
blocks and runs `node --check`. The covered assets are:

- `assets/web/dm/index.html`
- `assets/web/lan/index.html`
- `assets/web/dmcontrol/index.html`

If `node` is unavailable, the validation is blocked for browser assets.

## Final Report Requirements

Codex final reports for recovery work must include:

- Files inspected.
- Files changed.
- Exact gate/commands/branches/components migrated or repaired.
- What remains inline or unresolved, if applicable.
- Tests run and exact results.
- JS syntax-check command/result if a browser asset changed.
- Browser smoke status and notes; do not claim smoke if the user did not run it.
- Remaining risks.
- How `majorTODO.md` was updated, or why it was left alone.
- Single best next broad pass or next gate.
- `git status --short`.

For A0/docs/scripts-only tasks, report that no application source files,
tests, YAML game data, production config, deployment topology, or runtime
behavior were changed.

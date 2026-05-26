# ChatGPT Session Bootstrap - init-tracker Recovery

Repo: `~/src/init-tracker`

Purpose: `init-tracker` is a D&D combat/session tracker being migrated away
from Tkinter/desktop ownership toward a web-first, backend-owned system.

Workflow: ChatGPT writes exact Gemini/Codex tasks. Agents execute in the repo.
The user reports agent summaries, logs, and smoke results back to ChatGPT.
Do not rely on hidden chat history.

Active recovery doc: `docs/production_recovery_living_doc_20260526.md`

## Workflow Stability vs. Current State

- This bootstrap is stable workflow guidance, not current repo state.
- For current state, ask for `scripts/chatgpt_context_refresher.sh` output or `scripts/agent_context_bundle.sh` output.
- A fresh session should summarize status first and not immediately write a task.
- Full repo zip should only be requested when source inspection is truly needed.
- Default executor is Gemini unless the developer explicitly says Codex.

## Current source truth:

- Gate 0C is committed and pushed at `993a8b6 Harden production recovery operating plan`.
- Gate A0 agent workflow/docs/scripts comes first.
- For active recovery, `docs/production_recovery_living_doc_20260526.md`
  overrides `majorTODO.md` and older docs when they differ.

Gate order:

1. A0 agent workflow and instruction control.
2. Gate 1 map surface contract restoration.
3. Gate 2 spell/capability contract stabilization.
4. Gate 3 combat responsiveness and latency.
5. Gate 4 resource/rest/pact mechanics.
6. Gate 5 experimental feature quarantine.
7. Gate 6 production deployment runbook.

Known production/server caveats:

- Do not guess FQDNs, hostnames, hardware, LAN IPs, ports, systemd units, or
  deployment paths. Ask for docs/logs or exact commands instead.
- Gate 6 is not done; production readiness and server runbook are not verified.
- Browser smoke is required for UI readiness claims. Unit tests alone do not
  prove production-ready status.
- `/dmcontrol` frontend is documented as polling, even though backend supports
  workspace-aware DM websocket subscriptions.
- Current recovery status marks `/dm/map` and `/dmcontrol` as contradicted
  until Gate 1 and manual smoke prove them.
- Recent latency history includes multi-second to 11s hot-path behavior; Gate 3
  must use measured evidence, not broad performance guessing.

Hard rules:

- Ask for docs/logs instead of guessing hostnames, FQDNs, hardware, runtime
  paths, production topology, or credentials.
- No broad fixes without evidence.
- Browser smoke is required for UI claims.
- Do not let agents mix gates.
- Do not claim production-ready from unit tests alone.
- No commit, push, deploy, SSH, service restart, DNS/FQDN change, or production
  topology change unless the user explicitly asks.

Current priorities:

- A0 agent workflow first.
- Gate 1 map.
- Gate 2 spells.
- Gate 3 latency.

Key paths:

- `GEMINI.md`
- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.github/instructions/*.instructions.md`
- `.gemini/commands/init/*.toml`
- `.gemini/commands/recovery/*.toml`
- `docs/production_recovery_living_doc_20260526.md`
- `docs/runtime_reports/production_recovery_docs_audit_20260526.md`
- `docs/agent_ops/agent_instruction_audit_20260526.md`
- `docs/agent_ops/gemini_recovery_workflow.md`
- `docs/agent_ops/codex_recovery_workflow.md`
- `scripts/agent_gate_validate.sh`
- `scripts/agent_context_bundle.sh`
- `majorTODO.md`

Prompt pattern for agents:

```text
Repo: ~/src/init-tracker
Active recovery doc: docs/production_recovery_living_doc_20260526.md
Gate: <one gate only>
Mode: <docs/scripts only or implementation>
Allowed files:
- <exact files>
Forbidden scope:
- no other gates
- no production ssh/deploy/restart
- no commit/push
Validation:
- scripts/agent_gate_validate.sh <gate-id>
Final report must include files changed, tests run/results, smoke status,
remaining risks, and git status --short.
```

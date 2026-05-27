# ChatGPT Session Bootstrap - init-tracker Recovery

Repo: `~/src/init-tracker`

Purpose: `init-tracker` is a D&D combat/session tracker being migrated away
from Tkinter/desktop ownership toward a web-first, backend-owned system.

Workflow: ChatGPT writes exact Gemini/Codex tasks. Agents execute in the repo.
The developer reports agent summaries, logs, and smoke results back to ChatGPT.
Do not rely on hidden chat history.

Active recovery doc: `docs/production_recovery_living_doc_20260526.md`

## Workflow Stability vs. Current State

- This bootstrap is stable workflow guidance, not current repo state.
- For current state, ask for `scripts/chatgpt_context_refresher.sh` output or `scripts/agent_context_bundle.sh` output.
- A fresh session should summarize status first and not immediately write a task.
- Full repo zip should only be requested when source inspection is truly needed.
- Default executor is Gemini unless the developer explicitly says Codex.

## Source of Truth

- Current status, active gate, latest commit, and dirty state must come from the context refresher (`scripts/chatgpt_context_refresher.sh`).
- For active recovery, `docs/production_recovery_living_doc_20260526.md`
  overrides `majorTODO.md` and older docs when they differ.

### Example Gate Order (Verify current gate via context refresher)

1. A0 agent workflow and instruction control.
2. Gate 1 map surface contract restoration.
3. Gate 2 spell/capability contract stabilization.
4. Gate 3 combat responsiveness and latency.
5. Gate 4 resource/rest/pact mechanics.
6. Gate 5 experimental feature quarantine.
7. Gate 6 production deployment runbook.

## Hard Rules

- **No Guessing**: Ask for docs/logs instead of guessing hostnames, FQDNs, hardware, runtime paths, production topology, or credentials.
- **Evidence-Based**: No broad fixes without measured evidence.
- **Browser Smoke**: Browser smoke is required for UI claims. Unit tests alone do not prove production-ready status.
- **Gate Discipline**: Do not let agents mix gates.
- **Safety**: No commit, push, deploy, SSH, service restart, DNS/FQDN change, or production topology change unless the user explicitly asks.

## Key Paths

- `GEMINI.md`
- `AGENTS.md`
- `CLAUDE.md`
- `majorTODO.md`
- `docs/production_recovery_living_doc_20260526.md`
- `scripts/agent_gate_validate.sh`
- `scripts/chatgpt_context_refresher.sh`
- `scripts/agent_context_bundle.sh`

## Prompt Pattern for Agents

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

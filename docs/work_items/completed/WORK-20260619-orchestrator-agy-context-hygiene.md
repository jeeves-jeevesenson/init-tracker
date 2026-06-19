# WORK-20260619-orchestrator-agy-context-hygiene

Status: Completed
Type: Workflow/admin migration, not app development
Completed: 2026-06-19

## Goal

Persist AGY token discipline and Orchestrator context hygiene so AGY quota is reserved for actual init-tracker work and ChatGPT sessions do not become load-bearing volatile storage.

## Completed changes

- Added active AGY workflow doctrine in `docs/ai-workflows/agy.md`.
- Added Orchestrator context hygiene doctrine in `docs/ai-workflows/orchestrator-context-hygiene.md`.
- Replaced Gemini active workflow guidance with legacy/retired stop signs in `GEMINI.md` and `docs/ai-workflows/gemini.md`.
- Tightened `AGENTS.md` around AGY default execution, Codex explicit-only, Gemini retirement, volatile chat, and repo-durable source of truth.
- Tightened `docs/agent_tasks/templates/task-packet.md` with files-to-inspect-first, forbidden scope, AGY token budget, ephemeral context rule, stop conditions, and final report requirements.
- Added `docs/agent_tasks/templates/agy-token-discipline.md`.

## Validation

Developer ran:
- `git diff --check`

Result:
- clean

## Scope notes

No AGY was used.
No app code was touched.
No runtime/game/browser/deploy work was performed.

## Follow-up

Use these workflow docs for future Orchestrator and AGY task packets.
When a chat grows large or becomes load-bearing, persist a repo handoff before starting a fresh session.

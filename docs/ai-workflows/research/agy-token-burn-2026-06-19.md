# AGY Token Burn Research Brief

Created: 2026-06-19
Status: Durable research summary
Scope: Workflow guidance for init-tracker Orchestrator and AGY usage

## Purpose

This brief preserves the durable conclusions from the Orchestrator research pass on AGY token burn.

The original research was used to shape:
- `docs/ai-workflows/agy.md`
- `docs/ai-workflows/orchestrator-context-hygiene.md`
- `docs/agent_tasks/templates/task-packet.md`
- `docs/agent_tasks/templates/agy-token-discipline.md`
- Custom GPT Instructions / Knowledge

## Key conclusions

AGY token burn is worsened by:
- broad repo discovery
- vague tasks
- long-running agent sessions
- recursive scans and whole-repo grep
- large standing instruction files
- full log/file dumps
- noisy terminal output
- unnecessary subagents/background work
- unclear stop conditions
- asking the agent to plan and execute in the same large context
- treating chat history as durable project memory

## init-tracker policy derived from the research

AGY quota is for actual init-tracker work, not workflow optimization.

The Orchestrator GPT should do:
- context compression
- task scoping
- decision synthesis
- safe no-AGY shell patch drafting
- validation planning
- session handoff drafting

AGY should receive only:
- one bounded task
- exact files to inspect first
- exact allowed files
- explicit forbidden scope
- bounded validation
- token budget
- stop/logging conditions
- final report requirements

AGY must not be asked to:
- look around
- review the repo
- find anything else
- clean up related things
- run all tests
- continue until done

## Context hygiene conclusion

Using the Orchestrator GPT more heavily can save AGY tokens, but it creates another risk: ChatGPT sessions can become load-bearing volatile storage.

The developer deletes chats.

Therefore:
- chats are scratch RAM
- repo docs are durable memory
- important decisions must be written to the repo
- large/stale/load-bearing chats should end with a repo handoff and fresh session

## Durable implementation

The durable implementation is in:
- `docs/ai-workflows/agy.md`
- `docs/ai-workflows/orchestrator-context-hygiene.md`
- `docs/agent_tasks/templates/task-packet.md`
- `docs/agent_tasks/templates/agy-token-discipline.md`
- `docs/ai-workflows/generated/init-tracker-orchestrator-evergreen-knowledge.md`

## Source note

The full research happened in a ChatGPT session and included web/forum/source review. This file preserves the actionable conclusions needed by the repo. If deeper source provenance is needed later, repeat a fresh web research pass rather than relying on chat memory.

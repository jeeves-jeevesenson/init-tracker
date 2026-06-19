# AGY Workflow for init-tracker

Status: Active workflow doctrine
Created: 2026-06-19
Applies to: AGY task packets, Orchestrator GPT handoffs, workflow/admin planning

## Executor policy

AGY is the default execution agent for init-tracker.

Codex is explicit-only. Use Codex only when the developer explicitly asks for Codex or asks whether Codex is worth spending.

Gemini CLI is retired for this workflow. Gemini-era repo files are legacy compatibility artifacts only. Do not use Gemini as default, fallback, temporary migration executor, broad-analysis executor, or cheap executor.

## Repository is durable; chat is volatile

ChatGPT chats, uploaded file cards, pasted agent summaries, and conversational memory are volatile scratch space.

The repository is the only durable source of truth for:
- active work
- workflow decisions
- AGY task doctrine
- bug/work item status
- planning decisions
- smoke evidence summaries
- deploy notes
- unfinished work
- session handoffs

Anything important enough to rely on later must be written to the repo.

## Orchestrator / AGY split

The Orchestrator GPT should do:
- context compression
- task scoping
- decision synthesis
- no-AGY patch drafting
- bounded validation planning
- session handoff drafting

AGY should do:
- bounded repo edits
- bounded evidence capture
- bounded validation
- final report only

AGY should not be used for workflow optimization that the Orchestrator can turn into a safe shell patch.

AGY quota is for actual init-tracker work.

## AGY token burn causes to avoid

Avoid:
- vague tasks
- whole-repo discovery
- recursive tree scans
- broad grep over the repo
- reading full logs
- reading full large files when snippets or targeted commands are enough
- old plans, old bugs, completed work, runtime reports, and `majorTODO.md` unless explicitly named
- background/subagent work unless explicitly scoped
- long AGY sessions that accumulate context
- opportunistic cleanup
- running extra tests after required validation passes

Prefer:
- one narrow task per AGY run
- exact files to inspect first
- exact allowed files
- exact forbidden scope
- bounded validation
- command summaries with `grep`, `head`, `tail`, or `sed`
- stop-and-report when context is missing

## Required AGY task packet fields

Every AGY task must include:
- unique task ID
- repo path
- mode
- goal/gate/work item
- source document
- files to inspect first
- allowed files
- forbidden scope
- validation commands
- AGY token budget
- stop/logging conditions
- final report requirements

## Forbidden AGY prompts

Do not ask AGY to:
- “look around”
- “review the repo”
- “find anything else”
- “clean up related things”
- “do the obvious next fixes”
- “run all tests”
- “continue until done”

If AGY needs context outside the named scope, it must stop and report the missing context.

## New-session hygiene

Start a repo handoff and begin a fresh Orchestrator chat when:
- the chat contains decisions future work depends on
- the next answer relies on “what we discussed earlier”
- multiple task reports have accumulated
- the developer says the chat feels large or stale
- a bug, smoke result, deploy note, or work item decision is made
- the Orchestrator is summarizing chat more than current repo evidence

Before starting fresh, persist a compact handoff in the repo.

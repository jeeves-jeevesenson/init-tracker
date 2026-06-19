# Orchestrator Context Hygiene and Ephemeral Chat Rule

Status: Active workflow/admin doctrine
Created: 2026-06-19

## Core rule

Chat is volatile scratch space.

The repo is durable storage.

Do not leave important decisions, plans, smoke evidence, workflow doctrine, deploy notes, unfinished work, or “where we left off” only in ChatGPT.

## Developer expectation

The developer deletes chats and treats them as literal ephemeral storage.

The Orchestrator GPT may do more planning to conserve AGY tokens, but that creates a risk that the chat becomes load-bearing temporary memory.

That is not allowed.

## Required behavior

The Orchestrator must aggressively persist useful work into repo docs before:
- context grows large
- a new session is needed
- a decision becomes load-bearing
- AGY will need the context later
- the developer asks to stop or switch work
- a task completes or stalls

## Preferred durable locations

Use:
- `docs/work_items/current_work.md` for active status
- `docs/work_items/active/` for active work
- `docs/work_items/completed/` for completed work
- `docs/ai-workflows/` for workflow doctrine
- `docs/planning/living_docs/` for planning work
- `docs/bug_reports/` for bug evidence
- `logs/` for raw command/smoke output

## Session handoff contents

A useful handoff records:
- latest known commit
- dirty state
- active work item
- active gate
- completed work
- unfinished work
- commands run
- validation status
- smoke status
- deploy status, if relevant
- next safe action
- what not to do next

## AGY conservation

AGY is reserved for actual init-tracker work.

For workflow/admin changes, prefer:
1. Orchestrator drafts exact patch command.
2. Developer runs it.
3. Developer pastes validation output.
4. Orchestrator decides commit or next patch.

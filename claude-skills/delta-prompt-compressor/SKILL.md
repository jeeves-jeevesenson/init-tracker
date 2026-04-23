---
name: delta-prompt-compressor
description: Write short agent prompts that assume repo-wide conventions and reporting live in standing instructions. Use when creating a Codex or Claude task for a single pass and only the incremental task details should be included.
---

# Delta Prompt Compressor

## Purpose
Produce short, surgical agent prompts.

## Rules
- Assume repo-wide conventions, coding style, guardrails, and standard reporting already exist in standing instructions.
- Include only the delta for the current pass:
  - goal
  - relevant files or subsystem
  - pass-specific constraints
  - validation to run
  - any unusual reporting requirement not already covered elsewhere
- Do not restate evergreen repo norms unless this pass overrides them.

## Output style
Keep the prompt compact and directly pasteable into an agent.

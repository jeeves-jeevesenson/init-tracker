---
name: bounded-pass-planner
description: Plan one narrow engineering pass from current repo state, recent logs, and explicit user observations. Use when asked for the next implementation task, a handoff prompt, or a tightly scoped pass. Prefer one decisive slice over broad refactors.
---

# Bounded Pass Planner

## Purpose
Turn the current engineering situation into one clean, actionable pass.

## Operating rules
- Ground first on current repo state, recent logs/tests, and explicit user observations.
- Separate confirmed facts from suspicions.
- If a bug or performance issue is not yet measured, do not guess. First add instrumentation or capture evidence.
- Propose exactly one narrowly scoped pass.
- Preserve existing working behavior unless the task is explicitly about redesign.
- Prefer small decisive slices over broad refactors.

## Output shape
Produce:
1. Current grounded state
2. Primary goal for this pass
3. Files/subsystem to inspect
4. Pass-specific constraints and explicit "do not touch"
5. Lightweight validation
6. Required end-of-pass report
7. A short, paste-ready agent task

## Required end-of-pass report
- Files inspected
- Files changed
- Root cause found
- Exact fix applied
- Test results
- Remaining risk
- Single best next pass

See also:
- [TASK_TEMPLATE.md](TASK_TEMPLATE.md)
- [REPORT_TEMPLATE.md](REPORT_TEMPLATE.md)

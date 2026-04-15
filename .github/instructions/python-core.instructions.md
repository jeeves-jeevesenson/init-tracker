---
applyTo: "**/*.py"
---

# Python (Tkinter + LAN) instructions

## Design constraints
- Tkinter must remain responsive: do not block the UI thread.
- LAN server work should stay off the UI thread; use the existing queue/message passing patterns.
- Prefer smallest complete correct scoped solutions over smallest diffs.
- Large refactors are acceptable when they are the scoped and safest completion path.

## Changes involving combat state
- Treat combat state as the source of truth; ensure UI + LAN clients stay consistent.
- If you change turn logic / validation, consider both DM actions and player-originated actions.

## Execution behavior for implementation tasks
- If scope is already defined in-thread, do not ask the user to restate requirements.
- When scope is implementation-ready, perform minimal repo inspection and start implementation.
- Prefer one complete bounded migration slice over tiny incomplete edits.
- Avoid unnecessary stage-by-stage approval loops unless a true blocker exists.
- Do not stop after a single narrow path when adjacent in-scope Python paths are required for truthful completion.

## Validation expectations
- Run focused validation proportional to touched Python code and behavior.
- Do not default to indiscriminate whole-repo checks unless risk justifies broader coverage.

## Error handling & logging
- On user-facing errors, fail gracefully and add actionable log messages.
- Avoid noisy logs; prefer one clear line with context (what action, what inputs, what failed).

## Backwards compatibility
- Do not rename `dnd_initative_tracker.py`.
- Do not break existing YAML schemas or saved data expectations.
- Avoid changing LAN message shapes unless you maintain compatibility (e.g., new optional fields).

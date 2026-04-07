# Copilot Instructions — dnd-initiative-tracker

## Project summary
This repository is a Python desktop app (Tkinter) for the DM plus an optional LAN/mobile web client served via FastAPI + WebSockets.

- Tkinter UI runs on the main thread.
- LAN server runs on a background thread.
- Communication is queue-based.
- The main script filename is `dnd_initative_tracker.py` (historical typo). **Do not rename it.**

## Primary entry points
- `dnd_initative_tracker.py` — application entry point; main app class, combat flow, LAN controller/config
- `helper_script.py` — core UI and combat helpers
- `assets/web/` — LAN/mobile client UI
- `scripts/` — install/update/uninstall tooling
- `Spells/`, `Monsters/`, player/preset YAML — structured game data

---

## Global operating guidance

- Stay scoped to the user request.
- Prefer local repo evidence over generic theory.
- Keep changes small, targeted, and easy to review.
- Avoid unrelated churn or opportunistic refactors.
- If the request is planning/analysis only, do not force implementation.

Use standard Unix tools for discovery and prefer `grep -R` for recursive search.

---

## Architecture and safety constraints

- Keep Tkinter responsive; do not block the UI thread.
- Keep LAN server work off the UI thread; preserve queue/message passing behavior.
- Treat combat state as a source of truth across desktop and LAN/mobile flows.
- Be careful about host/client drift, reconnect behavior, and serialization/state cleanup.
- Preserve compatibility for saved state/config and YAML schemas unless explicitly requested.
- Preserve LAN trust boundaries; do not broaden internet exposure unless explicitly requested.
- Never expose secrets, tokens, credentials, or `.env` values.

---

## Validation expectations

Use the smallest verification loop that proves the requested outcome.

Default order:
1. targeted reproduction/inspection
2. targeted tests for touched behavior
3. adjacent checks for likely sibling paths
4. broader validation only when justified

Minimum check after code edits:
- `python -m compileall .`

`compileall` only checks syntax; pair it with behavior-focused validation for non-trivial changes.

---

## Repo-specific do-not-break rules

- Do not rename `dnd_initative_tracker.py`.
- Do not break existing YAML schemas without explicit migration direction.
- Do not break LAN message compatibility without an intentional compatibility plan.
- For data-heavy YAML changes, avoid mass reformatting unless explicitly requested.

---

## Anti-waste guidance

Unless the task requires it, avoid:
- broad repository tours when relevant files are already identified
- CI workflow/run deep dives for local code-focused requests
- full-repo lint/build/test loops before localizing the issue
- speculative rewrites not tied to user-requested outcomes

If investigation scope is uncertain, identify the minimum next file/path to inspect and continue incrementally.

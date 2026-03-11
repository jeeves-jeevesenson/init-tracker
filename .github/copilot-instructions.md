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

## How to work in this repo

Most work in this repository is assigned as a **structured Codex task** with sections like:

- Title
- Context
- User report
- Relevant files
- Plan
- Implementation notes
- Verification
- Acceptance criteria
- Non-goals
- Rollback plan

When a structured task is provided, **treat it as the active source of scope and completion criteria**.

### Important operating rule
If the task already provides:
- relevant files
- known leftover paths
- acceptance criteria
- verification steps
- explicit non-goals

then **start there immediately**.

Do **not** waste time on broad repo tours, generic CI investigation, or re-discovering scope unless repository evidence proves the task is wrong.

---

## Task priorities

Optimize for this order:

1. **Understand the exact requested behavior**
2. **Inspect the named files and nearby code paths**
3. **Find sibling/fallback/special-case paths before editing**
4. **Make the smallest safe complete fix**
5. **Prove it with targeted tests**
6. **Only then do broader validation if justified**

This repo favors **complete scoped fixes** over broad refactors.

---

## Completion standard

Do not declare a task complete just because the main path works.

For bugfix, parity, cleanup, consistency, or automation tasks, completion requires:

1. the main reported path is fixed
2. nearby sibling/fallback/special-case paths with the same bug pattern are handled or explicitly ruled out
3. old broken/generic behavior is no longer present in important active flows
4. targeted tests prove the new behavior
5. the final summary clearly states any remaining edge cases or residual risk

“Mostly fixed” is not done for parity work.

---

## Anti-waste rules

Unless the user explicitly asks, or the task explicitly depends on it, **do not spend time on**:

- reading the README for tightly scoped tasks
- broad repo tours when relevant files are already named
- GitHub Actions workflow browsing
- CI run / job log investigation
- broad architecture narration
- repo-wide lint/build/test before localizing the issue
- screenshots
- speculative rewrites

### CI rule
Do **not** inspect GitHub Actions workflows, workflow runs, or job logs unless:
- the task is about CI/build failure, or
- the user explicitly asks for CI investigation, or
- local verification directly depends on understanding a failing CI job

If the task is code-focused and local verification is available, stay local.

---

## Validation expectations

Use the smallest verification loop that proves the task is done.

### Default validation order
1. targeted reproduction / inspection
2. targeted tests for touched area
3. adjacent tests for sibling paths
4. broader validation only if justified

### Minimum validation
- Run `python -m compileall .` to catch syntax errors.
- Compileall is **not** a substitute for behavior verification.
- Prefer the smallest relevant test file(s) for the touched area.
- If you touched LAN or `assets/web/`, run the most relevant LAN/UI regression tests available.
- If generated audit/report files are part of the requested workflow, regenerate them only after core code/tests are passing.

### Test mindset
This repo does have useful targeted regression tests. Use them.

Do not act as if compileall alone is sufficient proof.

---

## How to interpret structured Codex tasks

### Relevant files
Treat these as the starting point, not a suggestion.

### Plan
Follow the plan unless repository evidence shows a better route.

### Implementation notes
These are important guardrails. Prefer them over generic engineering habits.

### Verification
Run the requested targeted checks first.

### Acceptance criteria
These are the done conditions. Do not silently weaken them.

### Non-goals
Respect them. Do not broaden the task unless necessary for correctness or safety.

### Rollback plan
Keep the patch shaped so rollback is realistic.

---

## Repo-grounded investigation rules

When investigating a scoped task:

- inspect the named files first
- search for old strings / old behaviors / duplicate handlers
- search for fallback paths
- search for special-case branches
- search for tests asserting the old behavior
- prefer shared canonical logic over more one-off logic

For parity and cleanup tasks, a leftover-path sweep is mandatory before declaring completion.

---

## Spell / YAML specific guidance

Spells, monsters, player presets, and related YAML are structured data, not freeform notes.

- Avoid mass reformatting.
- Treat YAML descriptions and structured metadata as intentional data.
- Use the YAML as authoritative for what a spell or feature is supposed to do unless the task says otherwise.
- Do not distort structured metadata just to fit an engine shortcut if a more explicit representation is possible.
- When implementing spell automation, check:
  - action economy
  - targeting/range
  - attack vs save behavior
  - scaling
  - riders/effects
  - ongoing state / expiration
  - test coverage for the lifecycle

For staged spell automation, do not stop after the first cast path if follow-up actions, cleanup, or expiry remain incomplete.

---

## UI / LAN guidance

For LAN/mobile work:

- preserve existing LAN protocol expectations unless explicitly changing them
- preserve compatibility with saved state/config where possible
- prefer server-side source of truth for combat/state
- do not move game-rule logic into the browser solely to improve UX text
- when changing player-facing logs/toasts/prompts, search for sibling variants so the app does not end up with mixed messaging styles

Do not take screenshots for this app.

---

## Code style

- Follow existing style.
- Keep line length around 120 where practical.
- Prefer type hints and docstrings for non-trivial logic.
- Keep changes minimal, targeted, and easy to review.
- Avoid drive-by refactors.
- Preserve backward compatibility for config files, saved state, and LAN protocol unless explicitly told otherwise.

---

## Collaboration style in this repo

When assigned a task:

1. Start with a short plan.
2. Work from the Codex task scope if one is provided.
3. Implement in small, reviewable commits when applicable.
4. Batch follow-up fixes cleanly if review reveals issues.

Do not substitute ceremonial progress updates for actual repo progress.

---

## Output expectations

For implementation work, final reporting should always include:

- **Root cause** — what broke and why
- **Fix** — what changed and why it is safe
- **Verification** — exact commands run and what passed
- **Files touched** — explicit list
- **Residual risk** — any remaining uncertainty or intentionally deferred edge case

If any known leftover path remains, say so plainly instead of implying full completion.

---

## Safety / networking

- LAN server is intended for trusted local networks only.
- Do not add features that encourage internet exposure unless explicitly requested.
- Never expose secrets, tokens, credentials, or `.env` values.
- Preserve existing trust boundaries and state ownership rules between desktop host and LAN clients.

# Gemini instructions for this repository

These are repo-local instructions for Gemini CLI and Gemini Code Assist.
They are written to keep Gemini focused, evidence-based, and consistent
with the direction the rest of this project's agent guidance already
encodes (see `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
and `.github/instructions/*.instructions.md`).

If anything here disagrees with current code or `majorTODO.md`, trust the
code/tracker first and update this file.

---

## Mission (permanent direction)

This repository is migrating away from a Tkinter/canvas-heavy desktop
host toward a production-ready, **headless/browser-first**, backend-owned
system.

- Headless + browser is the **permanent** runtime direction.
- Tkinter is **not** an end-state product goal. Treat it as a transitional
  compatibility surface that will be removed.
- Do not optimize for preserving Tk/desktop behavior as the long-term
  target. New work should not deepen tracker/desktop coupling.
- The desktop entrypoint still exists, but `serve_headless.py` +
  `INIT_TRACKER_HEADLESS=1` + `HeadlessRoot` (`tk_compat.py`) are the
  intended runtime path.

---

## Source of truth

Before making strong claims:

- inspect the **current repository state**
- treat current code + `majorTODO.md` as source of truth
- trust code/tests over older docs when they disagree
- update `majorTODO.md` honestly when repo state has changed

`majorTODO.md` is the durable platform tracker. Do not invent missing
branches, stale TODO items, or file paths/systems that are not actually
in the repo. If a tracker entry is stale, fix the tracker — do not
fabricate compatibility work to match it.

---

## When the task is a bug or performance issue

Bugs and performance complaints require **measured evidence** before a
fix is proposed.

Required before suggesting a code change for a bug/perf issue:

- a clear restatement of the symptom using only explicit evidence
- a reproduction path or the instrumentation that would produce one
- relevant logs, timings, or captured payloads (or a plan to capture them)
- a confirmed or strongly-narrowed root cause hypothesis

For complex issues, use the **runtime-observer** workflow (see
`docs/ai-workflows/runtime-debugging.md`) to capture evidence from
a real browser session before starting a fix pass.

If the issue is unmeasured, the pass should be about **adding
instrumentation or capturing evidence first**, not guessing at a fix.
Existing instrumentation hooks worth using:

- `LAN_PERF_DEBUG=1` for LAN/profile/cache timing
- `INITTRACKER_WS_DEBUG=1` for websocket lifecycle JSONL diagnostics
- focused `python3 -m unittest` runs under `tests/` for behavior pinning

Avoid speculative refactors framed as bugfixes.

---

## When the task is broad architecture / planning

Architecture, migration planning, repo-mapping, and direction-setting
work **may** be broad. For these:

- it is OK to inspect many files, scan whole subsystems, and produce
  large written analysis
- prefer concrete file/line references over generic claims
- separate **confirmed** from **suspected** clearly
- end with a concrete next bounded pass, not a sprawling roadmap

Bug fixes and small product slices should stay narrow regardless.

---

## Working style

Default to:

- minimal repo inspection for scoped tasks
- one broad, coherent, bounded pass
- focused validation
- clear end-of-pass reporting

Prefer:

- broad family extraction over tiny seam polish
- smallest **complete** scoped solution, not smallest diff
- one real ownership move per pass
- stable delegation/routing patterns across adjacent families

Avoid:

- repo-wide wandering on small tasks
- over-planning when scope is already implementation-ready
- micro-cleanup passes that do not materially reduce inline ownership
- unnecessary renames, comment cleanup, or abstraction churn

---

## Architecture direction

Prefer:

- backend-owned authority
- explicit contracts (see `player_command_contracts.py`)
- canonical state models
- testable helper/service seams (see `player_command_service.py`,
  `combat_service.py`)
- shrinking monolithic ownership hotspots in `dnd_initative_tracker.py`
  (especially `_lan_apply_action()`)

Do not:

- spread tracker/desktop coupling into new code
- add new desktop-first fallback paths unless absolutely required for a
  safe bounded pass
- keep long-lived dual ownership when a slice has already been migrated

The preferred extraction shape (when it fits) is documented in
`AGENTS.md` and `.github/skills/backend-family-extraction/SKILL.md`.

---

## YAML and saved-data discipline

- Do **not** break saved-data or YAML compatibility unless the task is
  explicitly a schema/data migration.
- Do **not** reformat YAML files in bulk (spacing, key ordering,
  quoting) unless requested.
- Touch only YAML files required for the task at hand.
- New schema fields should be additive and optional where possible.
- Folder READMEs under `Items/`, `Monsters/`, `Spells/`, `players/`,
  `presets/` are the schema documentation; defer to them.

If the task is documentation/schema work, YAML edits are in scope.
Otherwise skip YAML data churn.

---

## Hard guardrails

- Do **not** rename `dnd_initative_tracker.py` (the typo is intentional
  for compatibility).
- Do **not** commit or push unless explicitly asked.
- Keep reconnect, claims/auth, hidden-information handling, and
  persistence safety intact.
- Do not rewrite the map/tactical layer first unless the task explicitly
  requires it.
- Do not preserve desktop-first behavior as an end-state goal.
- Do not invent secrets, tokens, or machine-specific paths in any
  generated config.

---

## Validation expectations

Use focused validation proportional to the pass.

Default validation:

- `python3 -m py_compile` on edited Python files
- focused `python3 -m unittest tests.<module>` for the touched family
- command-contract / allowlist tests if those areas were touched
- adjacent focused regression tests when a family shares runtime paths

Do not default to indiscriminate whole-repo test sweeps unless risk
clearly justifies it. Be explicit about:

- real regressions vs. pre-existing failures
- environment blockers (missing deps, missing `pytest`, etc.)

If the change is UI/web only and you cannot drive a browser, say so
plainly instead of claiming success.

---

## End-of-pass report (required for substantial passes)

At the end of any non-trivial pass, report:

- files inspected
- files changed
- the symptom or scope addressed (and the evidence that justified it)
- exactly which branches/commands/components were touched
- what handlers / dispatchers / contracts were introduced or changed
- what tests were run and their results
- what remains rough or risky
- exactly how `majorTODO.md` was updated (or why it was left alone)
- the single best next broad pass

Do not claim a phase is complete unless code and focused validation
support that claim.

---

## Where to look first

- Repo direction + tracker: `majorTODO.md`
- Existing agent guidance: `AGENTS.md`, `CLAUDE.md`,
  `.github/copilot-instructions.md`,
  `.github/instructions/*.instructions.md`
- Backend authority hotspots: `dnd_initative_tracker.py`
  (`_lan_apply_action`), `player_command_service.py`,
  `player_command_contracts.py`, `combat_service.py`
- Headless host seam: `serve_headless.py`, `tk_compat.py`
  (`INIT_TRACKER_HEADLESS`, `HeadlessRoot`)
- Web surfaces: `assets/web/{dm,lan,shop,...}`
- Tests: `tests/`
- Repo-local Gemini infrastructure: `.gemini/agents/`,
  `.gemini/commands/init/`, `.gemini/settings.example.json`
- Workflow guide: `docs/ai-workflows/gemini.md`

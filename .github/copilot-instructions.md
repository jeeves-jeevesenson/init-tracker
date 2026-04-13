# Copilot Instructions — dnd-initiative-tracker

## Repository summary

This repository contains two important product tracks that now coexist:

1. **D&D Initiative Tracker product code**
   - Python desktop app for the DM using Tkinter
   - Optional LAN/mobile web client served through FastAPI + WebSockets
   - Structured YAML game data for spells, monsters, players, presets, and related content

2. **Orchestration / automation code**
   - OpenAI-backed planning and review
   - GitHub issue/task intake
   - Plain GitHub Copilot execution dispatch
   - Task/program state management
   - Inspection and notification flows

Treat the repository as the source of truth. Inspect the actual code before making implementation decisions.

---

## Important repo facts

- The historical main script filename is `dnd_initative_tracker.py` (misspelled). **Do not rename it** unless the user explicitly asks.
- Preserve YAML compatibility unless the task explicitly includes a migration plan.
- Preserve existing LAN/client compatibility unless the task explicitly changes message contracts.
- Do not assume the repo is cleanly separated; verify architecture from the code.

---

## Execution model

For automation/orchestrator work, assume this production model:

- **OpenAI** = planner / reviewer / continuation brain
- **orchestrator** = dispatcher / state machine / persistence / policy layer
- **plain GitHub Copilot** = execution worker
- **human** = reviewer / approver / escalation point

Do **not** depend on GitHub custom-agent launch as the required execution path.
Internal worker labels such as Initiative Smith or Tracker Engineer are orchestration metadata only unless the task explicitly says otherwise.

---

## Primary repo areas

Likely important areas include, but are not limited to:

- `dnd_initative_tracker.py` — application entry point, main app class, combat flow, LAN controller/config
- `helper_script.py` — core UI and combat helpers
- `assets/web/` — LAN/mobile and DM web UI
- `scripts/` — install/update/uninstall tooling
- `Spells/`, `Monsters/`, player/preset YAML — structured data
- `orchestrator/` — task/program automation, OpenAI integration, dispatch, persistence, inspection

Do not assume these are the only relevant files. Inspect before editing.

---

## Default working style

When implementation is requested, default to:

**inspect relevant files → implement scoped changes → run focused validation → report exact results**

Do this in one coherent pass unless there is a real blocker.

Do not turn straightforward implementation requests into planning-only responses when the repo and tools make implementation possible.

---

## Discovery guidance

Prefer deterministic repo inspection over guesswork.

Use standard Unix tools such as:

- `find`
- `grep -R`
- targeted file inspection
- existing tests
- existing docs and config

Do not invent file paths, classes, routes, schemas, or architecture.
Discover them from the repository first.

---

## Scope discipline

- Stay scoped to the user request.
- Prefer repo evidence over generic theory.
- Reuse existing patterns, models, routes, utilities, and tests where practical.
- Avoid speculative refactors not tied to the requested outcome.
- Large multi-file diffs are acceptable when they are the correct scoped solution.
- Do not create repeated approval loops unless blocked by true ambiguity, missing prerequisites, or scope risk.

---

## Anti-waste rules

- Do **not** ask the user to restate requirements already present in-thread.
- Do **not** paraphrase prompt text back unless clarifying a real ambiguity.
- Do **not** spend time on broad repo tours once the relevant paths are known.
- Do **not** default to “just planning” when implementation was requested.
- Do **not** assume a missing capability without first checking the repo or attempting the relevant operation.
- Do **not** split one coherent implementation into many tiny passes unless the task truly requires that.

---

## Tracker product engineering guardrails

When touching the D&D tracker application:

- Keep Tkinter responsive; do not block the UI thread.
- Keep server/network work off the UI thread.
- Preserve thread-safe queue/message-passing behavior where it already exists.
- Treat combat/session state as shared product truth across desktop and web flows.
- Be careful about:
  - desktop/web state drift
  - reconnect behavior
  - serialization and cleanup
  - LAN/mobile client compatibility
  - persistence/save/load consistency
- Preserve YAML schemas and saved-state compatibility unless a migration is intentionally included.
- Preserve LAN trust boundaries; do not broaden internet exposure unless explicitly requested.
- Do not casually break:
  - desktop DM workflows
  - LAN/mobile client flows
  - save/load behavior
  - existing web surfaces

---

## Migration guidance for the tracker product

The long-term product direction is toward:

- backend/service-owned state
- web-driven DM interface
- reduced Tkinter/canvas centrality
- preserved transition compatibility during migration

When working on migration slices:

- prefer moving authority into backend/service seams
- prefer shared canonical state over duplicated desktop/web ownership
- preserve hybrid operation where practical during transition
- do not attempt blind full rewrites unless explicitly requested
- document what becomes backend-owned versus what remains hybrid

---

## Orchestrator engineering guardrails

When touching the orchestrator:

- Preserve the plain Copilot execution path as the production default.
- Keep custom-agent concepts as metadata unless the task explicitly changes that.
- Favor deterministic, idempotent workflow transitions.
- Persist enough state to explain why the system is running, waiting, blocked, revising, or escalating.
- Avoid silent stalls.
- Surface blockers explicitly.
- Be careful about:
  - duplicate event handling
  - repeated webhook delivery
  - duplicate slice/task creation
  - stale PR/task/run linkage
  - race conditions around merge/continue logic
  - schema drift in structured OpenAI outputs
  - unsafe auto-merge or unsafe auto-confirm behavior

When using structured OpenAI response schemas:
- validate schema shape locally before making the API call
- ensure required fields and nullable fields are modeled correctly
- prefer explicit, predictable JSON artifacts over loosely formatted text

---

## Program-runner guidance

If the task touches autonomous execution/program flow:

- Think in terms of **program → slice → task → run → PR → review decision**
- One broad objective may span multiple bounded PR slices
- OpenAI review should evaluate actual evidence, not only PR summaries
- Continuation decisions should be explicit, such as:
  - continue
  - revise
  - audit
  - escalate
  - complete
- Preserve manual override capability
- Prefer conservative defaults for merge/approval policies unless the task explicitly loosens them

---

## Validation expectations

Use the smallest validation loop that proves the requested outcome.

Default order:
1. targeted reproduction or inspection
2. focused tests for touched behavior
3. adjacent checks for likely sibling paths
4. broader validation only when justified

Minimum syntax check after Python edits:
- `python -m compileall .`

`compileall` is not sufficient for non-trivial changes by itself.
Pair it with behavior-focused validation.

For orchestrator changes, prefer validating:
- task/program creation
- linkage persistence
- review artifact generation
- continuation decisions
- idempotency under repeated events
- inspection routes
- existing single-task flow compatibility

For tracker changes, prefer validating:
- touched API/UI behavior
- combat/session mutations
- save/load compatibility where relevant
- existing targeted tests for the touched subsystem

Distinguish clearly between:
- pre-existing failures
- regressions introduced by your changes

---

## Reporting expectations

When finished, report:

- exact files changed
- what was implemented
- what remains incomplete, hybrid, manual, or intentionally conservative
- validations run and results
- known risks
- best next follow-up pass

Be honest about limitations.
Do not overstate maturity from a broad first pass.

---

## Repo-specific do-not-break rules

- Do not rename `dnd_initative_tracker.py`.
- Do not break YAML schemas without an explicit migration path.
- Do not break LAN message compatibility without an intentional compatibility plan.
- Do not expose secrets, credentials, tokens, or `.env` values.
- Do not weaken security/approval controls blindly; revise them intentionally and explain the tradeoff.
- For data-heavy YAML changes, avoid mass reformatting unless explicitly requested.

---

## Efficiency guidance

Unless the task requires it, avoid:

- broad repository tours when the relevant files are already identified
- full-repo test/lint/build loops before localizing the change
- speculative architecture rewrites
- unrelated cleanup mixed into a scoped task
- turning a practical implementation request into process theater

If investigation scope is uncertain, identify the minimum next file/path to inspect and continue from there.

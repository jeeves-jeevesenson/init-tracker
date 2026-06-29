# WORK-20260628-command-queue-semantics: Command queue semantics

- **Status:** Active
- **Gate:** Command Queue Semantics Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded evidence/design task, or developer no-agent design patch if chosen.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-command-queue-spell-color`, completed in `fa1e79f` and closed in `72c8b57`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json`

## Migration Mode Override

The developer is in the middle of the server-runtime extraction migration.

The active strategic lane is:

**ASGI server first, runtime as a service.**

Do not recommend triaging unrelated bug inbox dirt, logs, cleanup, deploy, or random repo maintenance unless the developer explicitly asks.

Known unrelated dirt:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`

These are not blockers and are not this work item.

## Goal

Define the minimal command queue semantics needed before moving more mutations through the runtime facade.

This is an evidence/design work item. It must not implement queue infrastructure, migrate routes, or change runtime behavior.

## Current evidence

Bounded inspection found:

- `LanController.__init__` initializes the existing LAN action queue as `self._actions`.
- The WebSocket path acknowledges accepted action messages and enqueues them into `self._actions`.
- `LanController._tick` drains actions on the Tk thread, computes queue wait timing, and dispatches actions to tracker behavior.
- `ServerRuntimeFacade.submit_command(...)` currently handles the spell-color command synchronously by calling the tracker app hook directly.

## Design questions to answer

A future evidence/design task should answer:

1. Should runtime facade commands reuse the existing LAN action queue, introduce a separate runtime queue, or define a facade-owned abstraction over the existing queue first?
2. Which thread is authoritative for mutating tracker state?
3. What is the minimal command lifecycle: accepted, queued, dispatching, completed, failed?
4. Should synchronous HTTP routes wait for completion, return accepted, or use a hybrid model?
5. What failure behavior should be preserved for HTTP routes that currently map exceptions directly?
6. What observability is required now: queue depth, command age, dispatch duration, status map, log/debug trace fields?
7. Which next implementation slice is safest after semantics are defined?

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-command-queue-semantics.md`
- `docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json`
- `docs/work_items/completed/WORK-20260628-command-queue-spell-color.md`
- `docs/work_items/completed/WORK-20260628-command-queue-slice-selection.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`

## Evidence/design task intent

The future task should append a section named:

`## Command Queue Semantics Decision`

It should include:

1. Existing queue/threading evidence from named files.
2. Proposed minimal command lifecycle.
3. Proposed threading authority boundary.
4. Proposed HTTP command behavior for synchronous metadata routes versus async player/WebSocket actions.
5. Proposed failure and timeout semantics.
6. Proposed observability fields.
7. Exactly one next implementation candidate.
8. Proposed scope JSON shape and validation for that implementation candidate.

## Likely allowed edit files for the evidence/design task

The future AGY task should edit only:

- `docs/work_items/active/WORK-20260628-command-queue-semantics.md`

It may inspect only the named source files above. If more files are required, it must stop and report the exact missing file/path needed.

## Forbidden scope

- Do not edit app/runtime source.
- Do not edit `server_runtime.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit `server_app.py`.
- Do not edit `serve_headless.py`.
- Do not edit tests.
- Do not edit `docs/work_items/current_work.md` during evidence capture.
- Do not implement command queue infrastructure.
- Do not migrate routes.
- Do not change runtime behavior.
- Do not implement snapshot cache.
- Do not add background workers.
- Do not edit frontend assets.
- Do not edit YAML/data files.
- Do not edit production/deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future evidence/design task must produce:

1. A concise command queue semantics decision based on named repo files.
2. Clear threading authority statement.
3. Clear HTTP/WebSocket command lifecycle proposal.
4. Clear failure/timeout behavior proposal.
5. Clear observability proposal.
6. Exactly one recommended next implementation slice.
7. No source code changes.
8. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json` passes.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-command-queue-semantics.md docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json

## Completion criteria

- Queue semantics decision is written into this work item.
- No source code changes are made.
- `current_work.md` is updated only when closing this work item.

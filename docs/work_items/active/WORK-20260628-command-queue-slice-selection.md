# WORK-20260628-command-queue-slice-selection: Command queue slice selection

- **Status:** Active
- **Gate:** Command Queue Slice Selection Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded evidence task, or developer no-agent command inventory if chosen.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-runtime-facade-contracts`, completed in `2244f09`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json`

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

Inventory current mutating route/action seams and select exactly one low-risk command-queue candidate for the next implementation slice.

This is an evidence/planning work item. It must not implement a command queue, migrate routes, change app behavior, or edit runtime code.

## Current evidence

A bounded decorator search found:

- `server_app.py` currently exposes only health/readiness endpoints.
- `dnd_initative_tracker.py` has no decorator-style route registrations.
- `server_runtime.py` now exposes fail-closed command/snapshot facade contracts.

Therefore the route/action ownership seam must be identified from current repo files before choosing a queue slice.

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-command-queue-slice-selection.md`
- `docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `server_app.py`
- `serve_headless.py`
- `dnd_initative_tracker.py`

## Evidence task intent

The future bounded task should identify:

1. Where HTTP/server routes or local action endpoints are actually registered today.
2. Which paths/actions are mutating versus read-only.
3. Which mutating path is smallest and lowest risk for a first command-queue slice.
4. Which exact files a future implementation task would need.
5. Which focused tests already exist or would need to be added.
6. Why other candidates were rejected for the first slice.

## Selection criteria

Prefer a candidate that:

- is small and easy to test,
- has low gameplay-rule risk,
- has minimal frontend/UI impact,
- already has focused tests or can get focused tests,
- can pass through `ServerRuntimeFacade.submit_command()` later without broad route migration,
- does not require tactical map snapshot changes.

Avoid candidates that:

- touch tactical map rendering,
- touch monster/player combat rules deeply,
- require broad frontend smoke,
- require workspace-aware snapshot behavior,
- require production/deploy changes.

## Likely allowed edit files for the evidence task

The future AGY task should edit only:

- `docs/work_items/active/WORK-20260628-command-queue-slice-selection.md`

It may inspect the named source files above. If it needs to inspect additional files to locate routes, it must report the exact missing file/path and stop or request an expanded scope.

## Forbidden scope

- Do not edit app/runtime source.
- Do not edit `server_runtime.py`.
- Do not edit `server_app.py`.
- Do not edit `serve_headless.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit tests.
- Do not edit `docs/work_items/current_work.md` during evidence capture.
- Do not implement command queue.
- Do not migrate gameplay routes.
- Do not implement snapshot cache.
- Do not edit frontend assets.
- Do not edit combat rules, player command logic, monster control behavior, tactical map behavior, YAML data, or production deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future evidence task must produce:

1. A concise route/action inventory based on named repo files.
2. A mutating/read-only classification for discovered candidates.
3. Exactly one recommended first command-queue implementation slice.
4. Exact proposed files for that future implementation slice.
5. Exact proposed validation for that future implementation slice.
6. A clear “not selected yet” list for higher-risk candidates.
7. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json` passes.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-command-queue-slice-selection.md docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json

## Completion criteria

- The selected candidate and evidence are written into this work item.
- No source code changes are made.
- `current_work.md` is updated only when closing this work item.

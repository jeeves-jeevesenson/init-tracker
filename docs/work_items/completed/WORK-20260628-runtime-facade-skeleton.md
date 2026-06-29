# WORK-20260628-runtime-facade-skeleton: Runtime facade skeleton

- **Status:** Completed
- **Gate:** Runtime Facade Skeleton Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded task packet, or developer no-agent patch if chosen.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-server-first-health-shell`, completed in `210a84e`.

## Migration Mode Override

The developer is in the middle of a large server-runtime extraction migration.

The active strategic lane is:

**ASGI server first, runtime as a service.**

Do not recommend triaging unrelated bug inbox dirt, logs, cleanup, deploy, or random repo maintenance unless the developer explicitly asks.

Known unrelated dirt:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`

These are not blockers and are not this work item.

## Goal

Create the smallest runtime facade skeleton behind the new server app factory seam.

This is a narrow foundation task. It should define the object/interface that the ASGI app can hold in `app.state`, without moving gameplay routes yet.

## Source documents to read first

- `AGENTS.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-runtime-facade-skeleton.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_app.py`
- `dnd_initative_tracker.py`
- `serve_headless.py`

## Forbidden scope

- Do not triage unrelated bug inbox dirt.
- Do not edit `logs/context/`.
- Do not migrate gameplay routes.
- Do not implement command queue.
- Do not implement snapshot cache.
- Do not edit frontend assets.
- Do not edit combat rules, player command logic, monster control behavior, tactical map behavior, YAML data, or production deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future implementation pass must prove:

1. The app factory can own or reference a runtime facade object.
2. The facade skeleton is narrow and behavior-preserving.
3. Existing `serve_headless.py` behavior is preserved.
4. Health/readiness behavior from the previous slice still passes.
5. No gameplay route migration is performed.
6. Validation is scoped and timeout-bounded.

## Validation for this opening commit

Run:

    git status --short
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-runtime-facade-skeleton.md

## Completion criteria

- Runtime facade skeleton implementation evidence is written back to this work item.
- `current_work.md` is updated when complete.
- Developer smoke is only required if runtime/server behavior needs a browser claim.

## Implementation Evidence (Pending Developer Review)

- Added `server_runtime.py` with a narrow `ServerRuntimeFacade` skeleton that stores the existing LAN controller reference and exposes lifecycle readiness through `start()`, `shutdown()`, and `is_ready()`.
- Updated `server_app.py` so `create_app()` stores the facade on `app.state.runtime` and the lifespan hook starts/shuts it down alongside existing readiness state.
- Added focused tests in `tests/test_server_app.py` for app factory facade ownership, lifespan readiness transitions, and existing health/readiness endpoints.

## Scope Guard Evidence

Run before commit:

    timeout 10s python3 scripts/agent_scope_validate.py docs/agent_tasks/scopes/examples/runtime-facade-skeleton-scope.example.json

The scope guard must pass before this implementation is committed.


## Completion Evidence

- Completed in `ac210c6`.
- Added `server_runtime.py` with narrow `ServerRuntimeFacade` lifecycle/readiness skeleton.
- Wired `create_app()` to store the facade on `app.state.runtime`.
- Preserved existing health/readiness behavior.
- Added focused tests in `tests/test_server_app.py`.
- Validation passed before commit:
  - `python3 -m py_compile server_app.py server_runtime.py serve_headless.py dnd_initative_tracker.py`
  - `.venv/bin/python -m pytest tests/test_server_app.py`
  - `scripts/agent_scope_validate.py docs/agent_tasks/scopes/examples/runtime-facade-skeleton-scope.example.json` before staging
- No gameplay route migration, command queue, snapshot cache, frontend work, unrelated inbox dirt, or `logs/context/` edits.

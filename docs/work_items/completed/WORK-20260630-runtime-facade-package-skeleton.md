# WORK-20260630-runtime-facade-package-skeleton: Add init_tracker_server package skeleton

## Status

Completed.

## Type

Focused implementation slice.

## Goal

Add the initial `init_tracker_server/` package skeleton and preserve `server_app.create_app` compatibility without changing gameplay route behavior, queue semantics, command migration behavior, WebSocket behavior, snapshot/cache behavior, or deployment topology.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Initial `HEAD` evidence:

```text
00600e4
```

The current-work ledger was `Idle` at the start of this pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-plan.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-readiness.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_app.py`
- `server_runtime.py`
- `serve_headless.py`
- `tests/test_server_health.py`
- `tests/test_headless_host.py`

## Files Changed

- `server_app.py`
- `tests/test_server_health.py`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`

## Package Files Created

- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`

## Implementation Notes

`init_tracker_server.app` now owns the package-level `create_app` and `app_lifespan` definitions. The moved factory preserves the existing app-state initialization, runtime facade construction, lifespan readiness toggle, and `/health`, `/api/health`, `/ready`, and `/api/ready` route behavior.

`server_app.py` remains as a compatibility shim that re-exports `create_app` and `app_lifespan` from `init_tracker_server.app`, preserving existing imports such as `from server_app import create_app`.

No route migration, queue behavior, `ServerRuntimeFacade` behavior, WebSocket behavior, snapshot/cache behavior, gameplay/combat mutation behavior, deployment config, hostnames, ports, process topology, or launcher behavior was changed.

## Tests Updated

`tests/test_server_health.py` now exercises both `init_tracker_server.app.create_app` and `server_app.create_app` against the same health/readiness expectations and verifies the legacy shim re-exports the package factory.

`tests/test_headless_host.py` was not changed.

## Validation

Required validation was run after the implementation and ledger updates:

- `python3 -m py_compile server_app.py tests/test_server_health.py tests/test_headless_host.py init_tracker_server/__init__.py init_tracker_server/app.py`
- `.venv/bin/python -m unittest tests/test_server_health.py tests/test_headless_host.py`
- `timeout 10s git diff --check`
- `git status --short`

Full command output is recorded in the final response for this pass.

## Remaining Inline / Out Of Scope

All gameplay routes remain where they were before this pass. No branches or commands were migrated out of `dnd_initative_tracker.py`, and no command dispatchers, command constants, queue adapters, snapshot/cache APIs, or WebSocket/event publication paths were introduced or changed.

## Risks / Rough Edges

This is package-boundary plumbing only. `ServerRuntimeFacade` still lives in `server_runtime.py`; future runtime/package ownership should happen in a separate compatibility-preserving slice.

## Next Broad Pass

The best next broad pass is a runtime facade ownership/import-boundary slice: introduce package-owned runtime imports while preserving `server_runtime.py` compatibility and without normalizing command names, result keys, trace events, or queue semantics.

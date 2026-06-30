# WORK-20260630-runtime-facade-package-boundary-plan: App-host/runtime-service package-boundary planning

## Status

Completed.

## Type

Planning/evidence only. No app/source/test implementation.

## Goal

Create a durable app-host/runtime-service package-boundary plan for the next server-runtime extraction phase. Define what an `init_tracker_server/` package boundary should eventually own, what must remain as compatibility shims, and the safest first implementation slice after planning.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Initial `HEAD` evidence:

```text
a37a83c WORK-20260630-runtime-facade-package-boundary-readiness: select package boundary planning
```

The current-work ledger was `Idle` at the start of this pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-readiness.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_app.py`
- `server_runtime.py`
- `serve_headless.py`
- `dnd_initative_tracker.py`, limited to host/lifecycle/server startup references
- `tests/test_server_health.py`
- `tests/test_headless_host.py`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-plan.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`

## Package-Boundary Plan

Durable plan path:

- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`

Proposed target package:

- `init_tracker_server/`

Proposed module boundary:

- `init_tracker_server/__init__.py`: curated public exports.
- `init_tracker_server/app.py`: FastAPI app factory, lifespan wiring, app-state initialization, health/readiness routes.
- `init_tracker_server/lifespan.py`: optional later split for startup/shutdown orchestration if needed.
- `init_tracker_server/runtime.py`: eventual home of `ServerRuntimeFacade` lifecycle and route-facing runtime service API.
- `init_tracker_server/commands.py`: eventual home of command/result/trace/snapshot contract dataclasses and command constants.
- `init_tracker_server/queue_boundary.py`: eventual home of the LanController queue adapter and queue telemetry semantics.
- `init_tracker_server/snapshots.py`: later read-model and cache contract boundary.
- `init_tracker_server/events.py`: later event/WebSocket publication boundary.
- `init_tracker_server/compat.py`: temporary compatibility bridge for legacy imports and tracker-hosted startup.
- `init_tracker_server/routes/`: later route modules only after route migration is explicitly scoped.

## Boundary Decisions

### App host

The app host should eventually own FastAPI construction, ASGI lifespan, readiness state, runtime service attachment, health/readiness endpoints, server-host import stability, and future route registration strategy.

It should not own gameplay mutation, queue semantics, tactical snapshot construction, WebSocket fanout internals, or legacy Tk/LanController details.

### Runtime facade

The runtime facade should eventually live behind `init_tracker_server.runtime` and own `start()`, `shutdown()`, `is_ready()`, command submission, command trace state, snapshot read API shape, and adapter selection between legacy LanController authority and a future backend-owned runtime.

It should not accumulate route-specific HTTP response behavior.

### Queue command boundary

The queue command boundary should eventually live under `init_tracker_server.commands` and `init_tracker_server.queue_boundary`. It should own command contracts, command constants/action names, lifecycle status constants, trace shape, timeout/error conventions, and the temporary legacy queue adapter.

Current command names, result keys, trace event names, and spell-color direct-facade behavior must be preserved until separately scoped.

### Snapshot/read-model boundary later

Snapshot/read-model ownership should wait. Current `RuntimeSnapshotRequest` and `RuntimeSnapshotResult` exist, but `ServerRuntimeFacade.read_snapshot(...)` fails closed with `NotImplementedError`. The later boundary should define combat-lite versus tactical/map contracts, workspace-aware tactical access, cache invalidation, and freshness expectations.

### Event/WebSocket publication boundary later

Event/WebSocket publication should wait. Current WebSocket/action dispatch remains LanController-owned and uses `ws.action.dispatch.start` / `ws.action.dispatch.end` trace names. A later package boundary should define server-owned publication APIs, fanout/backpressure, event contracts, and compatibility for existing trace names.

## Compatibility Shims

`server_app.py` should remain a compatibility import location for existing callers. The durable end state is package-owned app factory plus `server_app.py` shim, preserving `server_app.create_app(...)`, app-state initialization, lifespan behavior, and health/readiness routes.

`serve_headless.py` should remain the developer smoke launcher. It currently sets `INIT_TRACKER_HEADLESS=1` before importing the tracker, constructs `InitiativeTracker()`, optionally starts the existing LAN server path, and enters the headless mainloop. The first package implementation slice should not change it.

The first implementation slice should not move route registration, Uvicorn startup/stop ownership, facade command dispatch, command dataclasses/constants, LanController queue logic, snapshot/cache logic, WebSocket fanout, gameplay/combat mutation helpers, production runbooks, or topology.

## Current-State Evidence

### Host/lifecycle

- `server_app.py` defines `create_app(lan_controller=None)`.
- `server_app.py` imports `ServerRuntimeFacade` from `server_runtime.py`.
- `server_app.py` creates `FastAPI(lifespan=app_lifespan)`.
- `server_app.py` initializes `app.state.ready`, `app.state.lan_controller`, and `app.state.runtime`.
- `server_app.py` lifespan starts/shuts down the runtime facade and toggles readiness.
- `server_app.py` owns `/health`, `/api/health`, `/ready`, and `/api/ready`.
- `dnd_initative_tracker.py` imports `create_app` from `server_app`, assigns `self._fastapi_app`, assigns `self._runtime`, registers routes/static mounts, seeds snapshots, and starts Uvicorn in a LanController-owned thread.
- `serve_headless.py` remains a launcher around the existing tracker/LAN lifecycle, not the ASGI app owner.

### Facade/command inventory

- `server_runtime.py` currently contains runtime command, result, trace, and snapshot dataclasses; status constants; command constants; and `ServerRuntimeFacade`.
- `ServerRuntimeFacade` owns lifecycle readiness, command submission, queue submission, exception mapping, trace state, and fail-closed snapshot reads.
- Migrated queue-backed routes include facing, aura overlays, combatant place, AoE remove/move, obstacle/terrain/elevation cells, map settings, backgrounds, hazards, and features.
- Spell color uses the facade command boundary but is not queue-backed.
- Result keys and action names remain family-specific and should not be normalized during package-boundary skeleton work.

### Health/readiness and headless tests

- `tests/test_server_health.py` imports `create_app` from `server_app` and verifies factory construction, lifespan readiness true/false transitions, health endpoint payloads, and unready `/ready` HTTP 503 behavior.
- `tests/test_headless_host.py` verifies `HeadlessRoot`, `INIT_TRACKER_HEADLESS` detection, desktop-surface guards, full headless `InitiativeTracker()` construction, LAN startup, `/dm` HTTP 200, LAN stop, and clean mainloop shutdown.
- `grep -n "serve_headless" tests/test_headless_host.py` returned no matches; the test protects the headless runtime seam rather than the launcher module name.

## Proposed Phased Package Plan

### Phase 1: package skeleton / app factory shim only

Introduce `init_tracker_server/` and establish the app factory/lifespan/health-readiness import boundary. Preserve `server_app.create_app(...)`, route registration, Uvicorn lifecycle, runtime facade behavior, command semantics, and response shapes.

### Phase 2: runtime facade ownership/import boundary

Move or centralize `ServerRuntimeFacade` and command contract ownership under the package while preserving `server_runtime.py` compatibility imports. Preserve command constants, action names, result keys, timeout/error mapping, trace behavior, and route behavior.

### Phase 3: snapshot/cache/event/WebSocket consolidation

Define package-owned snapshot/read-model and event/WebSocket boundaries. Split this into separate implementation items unless later evidence proves they can be safely coupled.

## Recommended First Implementation Slice

Recommended next work item:

- ID: `WORK-20260630-runtime-facade-package-skeleton`
- Title: Add init_tracker_server package skeleton and app factory compatibility shim
- Type: implementation

## Acceptance Criteria For Recommended First Slice

- `init_tracker_server/` package exists with a minimal app-factory boundary.
- `server_app.create_app(...)` compatibility is preserved.
- Existing health/readiness response behavior is preserved.
- `serve_headless.py` still works as the developer smoke launcher.
- No gameplay route behavior changes.
- No command migration.
- No queue semantics changes.
- No WebSocket changes.
- No snapshot/cache changes.
- No gameplay/combat mutation changes.
- No deploy/topology changes.
- Bounded validation is run:
  - `python3 -m py_compile server_app.py`
  - `python3 -m py_compile init_tracker_server/__init__.py init_tracker_server/app.py`
  - `timeout 30s python3 -m unittest tests.test_server_health`
  - `timeout 120s python3 -m unittest tests.test_headless_host`
  - `timeout 10s git diff --check`

## Forbidden Scope For Recommended First Slice

- Do not migrate routes.
- Do not change queue semantics.
- Do not change WebSocket behavior.
- Do not change snapshot/cache behavior.
- Do not change gameplay/combat mutation behavior.
- Do not change deploy/topology behavior.
- Do not rename command constants, action names, result keys, or trace events.
- Do not convert spell color to queue-backed behavior.
- Do not move Uvicorn startup/stop ownership.
- Do not modify `serve_headless.py` unless a later task explicitly authorizes launcher changes.

## Validation

Required validation for this planning pass:

- `git status --short`
- `timeout 10s git diff --check`

Validation output is recorded in the final report for this pass.

## Stop Conditions

No stop condition was hit while drafting this plan.

The ledger was Idle, readiness/inventory/checkpoint docs were present, the package-boundary plan did not require source/test edits, and host/lifecycle evidence was determinable from the named files.

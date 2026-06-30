# Server Runtime Package Boundary Plan - 2026-06-30

## Status

Planning/evidence document. No app, source, test, route, queue, snapshot, WebSocket, deployment, or topology implementation is authorized by this document.

## Target Package Boundary

Proposed package name:

- `init_tracker_server/`

The package should become the stable import boundary for server-hosted runtime work. It should not become a dumping ground for tracker internals. Its purpose is to own the ASGI host boundary, define the runtime-service contracts the ASGI layer may call, and hide temporary legacy adapter details behind explicit modules.

### Proposed modules

- `init_tracker_server/__init__.py`: package marker and narrowly curated public exports.
- `init_tracker_server/app.py`: FastAPI app factory, lifespan wiring, app-state initialization, and health/readiness route attachment.
- `init_tracker_server/lifespan.py`: optional later split for startup/shutdown orchestration if `app.py` grows beyond factory glue.
- `init_tracker_server/runtime.py`: eventual home of `ServerRuntimeFacade` and runtime-service lifecycle methods.
- `init_tracker_server/commands.py`: eventual home of `RuntimeCommand`, `RuntimeCommandResult`, `RuntimeCommandTrace`, lifecycle status constants, command constants, and command-boundary error/timeout conventions.
- `init_tracker_server/queue_boundary.py`: eventual home of the legacy LanController queue adapter, action-state polling, timeout mapping, and queue telemetry collection.
- `init_tracker_server/snapshots.py`: later read-model contract boundary for `RuntimeSnapshotRequest`, `RuntimeSnapshotResult`, combat-lite snapshots, tactical/map snapshots, and cache invalidation rules.
- `init_tracker_server/events.py`: later event/WebSocket publication boundary for server-originated publish semantics, fanout policy, and backpressure.
- `init_tracker_server/compat.py`: temporary compatibility helpers that bridge old import locations and legacy tracker-hosted startup without leaking tracker internals into the app host.
- `init_tracker_server/routes/`: later route modules only after the package host boundary exists and route migration is explicitly authorized.

### App-host lifecycle ownership

The app-host boundary should eventually own:

- FastAPI app construction.
- ASGI lifespan startup/shutdown.
- `app.state.ready` semantics.
- runtime service creation and attachment to `app.state.runtime`.
- health/readiness endpoint registration.
- server-host import stability.
- route registration strategy for future packaged route modules.

The app host should not own gameplay mutation, queue semantics, tactical snapshot construction, WebSocket fanout internals, or legacy Tk/LanController details. Those must sit behind runtime, queue, snapshot, and event boundaries.

### RuntimeFacade ownership

`ServerRuntimeFacade` should eventually live behind `init_tracker_server.runtime`. It should own:

- `start()`, `shutdown()`, and `is_ready()`.
- command submission as the route-facing mutation gateway.
- command traces and route-facing observability state.
- snapshot read API shape, even while current `read_snapshot(...)` fails closed.
- adapter selection between legacy LanController authority and future backend-owned runtime authority.

The facade should not keep growing route-specific HTTP response logic. Route handlers should validate request data, call the facade, and map facade results/errors to current response shapes until response contracts are separately normalized.

### Queue command boundary ownership

The command boundary should eventually live under `init_tracker_server.commands` and `init_tracker_server.queue_boundary`.

It should own:

- command contract dataclasses.
- command constants/action names.
- command lifecycle status constants.
- timeout/failure/completion trace shape.
- route-facing exception conventions for timeout, validation/domain failure, and unexpected runtime failure.
- the temporary legacy queue adapter that submits to LanController `_actions` and reads `_action_states`.

It must preserve current queue semantics until a separate command-normalization item is opened. Do not rename action names, result keys, trace events, or command constants as part of the package skeleton.

### Snapshot/read-model boundary later

Snapshot/read-model ownership should be a later package phase. The current `RuntimeSnapshotRequest` and `RuntimeSnapshotResult` exist in `server_runtime.py`, but `ServerRuntimeFacade.read_snapshot(...)` currently fails closed with `NotImplementedError`.

The later snapshot boundary should define:

- combat-lite versus tactical/map snapshot contracts.
- workspace-aware tactical snapshot access for `/dm/map` and `/dmcontrol`.
- cache invalidation rules.
- read-side freshness expectations.
- when ordinary combat polling must avoid tactical payload construction.

No snapshot/cache movement belongs in the first implementation slice.

### Event/WebSocket publication boundary later

Event/WebSocket publication should also be a later package phase. Current evidence shows LanController-owned WebSocket/action dispatch and `ws.action.dispatch.start` / `ws.action.dispatch.end` trace names.

The later event boundary should define:

- server-owned publication API shape.
- WebSocket fanout and backpressure policy.
- event names and payload contracts.
- bridge behavior while LanController still owns active WebSocket state.
- compatibility policy for existing trace event names.

No WebSocket or event publication changes belong in the first implementation slice.

## Compatibility Shims

### `server_app.py`

`server_app.py` should remain a compatibility import location for existing callers.

In Phase 1, the safe target is:

- keep `server_app.create_app(...)` available with the same signature;
- preserve `app_lifespan` availability if tests or local imports rely on it;
- preserve `app.state.ready`, `app.state.lan_controller`, and `app.state.runtime` initialization semantics;
- preserve `/health`, `/api/health`, `/ready`, and `/api/ready` response behavior;
- avoid route registration changes.

The preferred implementation shape is to move or mirror the app factory into `init_tracker_server.app`, then make `server_app.py` a thin compatibility shim that re-exports the package-owned factory. If that creates avoidable churn, the first slice may instead add the package skeleton with a package-level wrapper that delegates to existing `server_app.create_app(...)`; however, the durable end state is package-owned app factory plus `server_app.py` shim.

### `serve_headless.py`

`serve_headless.py` should remain the developer smoke launcher for now.

It currently sets `INIT_TRACKER_HEADLESS=1` before importing `dnd_initative_tracker`, constructs `InitiativeTracker()`, optionally starts the existing LAN server path, and enters the headless mainloop. That makes it a valuable compatibility launcher while the server package boundary is introduced.

The first implementation slice must not change this launcher. Later work can add a server-owned launcher only after app-host ownership is proven and after a separate task defines migration behavior.

### What should not move first

The first implementation slice should not move:

- route registration from `dnd_initative_tracker.py`;
- Uvicorn thread startup/stop ownership from LanController;
- `ServerRuntimeFacade` command dispatch logic;
- command dataclasses/constants;
- LanController `_actions` / `_action_states` queue logic;
- snapshot/cache logic;
- WebSocket client/fanout logic;
- gameplay/combat mutation helpers;
- production runbooks or topology.

## Current-State Evidence

### Host/lifecycle evidence

- `server_app.py` defines `create_app(lan_controller=None)`.
- `server_app.py` imports `ServerRuntimeFacade` from `server_runtime.py`.
- `server_app.py` creates `FastAPI(lifespan=app_lifespan)`.
- `server_app.py` initializes `app.state.ready = False`, `app.state.lan_controller = lan_controller`, and `app.state.runtime = ServerRuntimeFacade(lan_controller=lan_controller)`.
- `server_app.py` lifespan starts the runtime facade, sets readiness true, then clears readiness and shuts down the facade on exit.
- `server_app.py` owns `/health`, `/api/health`, `/ready`, and `/api/ready`.
- `dnd_initative_tracker.py` LanController startup lazily imports FastAPI/Uvicorn dependencies, imports `create_app` from `server_app`, creates `self._fastapi_app = create_app(lan_controller=self)`, assigns `self._runtime = self._fastapi_app.state.runtime`, registers routes/static mounts on that app, and starts Uvicorn in a LanController-owned thread.
- `serve_headless.py` is not the ASGI app owner; it is the headless compatibility launcher around the existing tracker/LAN lifecycle.

### Facade/command inventory evidence

- `server_runtime.py` currently contains `RuntimeCommand`, `RuntimeCommandResult`, `RuntimeCommandTrace`, `RuntimeSnapshotRequest`, `RuntimeSnapshotResult`, command status constants, and command constants.
- `ServerRuntimeFacade` owns `start()`, `shutdown()`, `is_ready()`, `_submit_to_lan_queue(...)`, `_raise_mapped_exception(...)`, `submit_command(...)`, `last_command_trace`, and fail-closed `read_snapshot(...)`.
- The current migrated route pattern is `FastAPI route -> ServerRuntimeFacade.submit_command(...) -> LanController queue/Tk authority -> legacy mutation -> response/snapshot/trace`.
- Queue-backed migrated commands include facing, aura overlays, combatant place, AoE remove/move, obstacle/terrain/elevation cells, map settings, backgrounds, hazards, and features.
- Spell color is a facade command but is not queue-backed; it calls the app helper through `lan_controller.app`.
- Result data keys remain family-specific, including `place_result`, `remove_result`, `move_result`, `obstacle_result`, `terrain_result`, `elevation_result`, `settings_result`, `background_result`, `remove_background_result`, `reorder_background_result`, `hazard_result`, and `feature_result`.
- Trace event naming remains LanController/WebSocket-shaped for queue dispatch, including `ws.action.dispatch.start` and `ws.action.dispatch.end`.

### Health/readiness and headless-host test evidence

- `tests/test_server_health.py` imports `create_app` from `server_app`.
- `tests/test_server_health.py` verifies factory construction, initial unready state, `lan_controller` defaulting to `None`, lifespan readiness true inside `TestClient`, readiness false after lifespan shutdown, health endpoint responses, and unready `/ready` returning HTTP 503.
- `tests/test_headless_host.py` verifies `HeadlessRoot` scheduling behavior.
- `tests/test_headless_host.py` verifies `INIT_TRACKER_HEADLESS` truthy/falsy detection.
- `tests/test_headless_host.py` verifies desktop-only runtime surfaces are gated in headless mode.
- `tests/test_headless_host.py` runs a subprocess that sets `INIT_TRACKER_HEADLESS=1`, imports the tracker, constructs `InitiativeTracker()`, starts LAN on `127.0.0.1:18801`, hits `/dm`, expects HTTP 200, stops LAN, quits the headless mainloop, and expects clean thread shutdown.
- `grep -n "serve_headless" tests/test_headless_host.py` returned no matches, so the test protects the headless runtime seam directly rather than the `serve_headless.py` module name.

## Proposed Phased Package Plan

### Phase 1: package skeleton and app factory shim only

Goal:

- Introduce `init_tracker_server/` as the future package boundary.
- Move or wrap only the app factory/lifespan/health-readiness shell.
- Keep `server_app.create_app(...)` compatibility intact.
- Preserve all route registration, Uvicorn lifecycle, runtime facade behavior, command semantics, and response shapes.

Allowed implementation shape:

- Add `init_tracker_server/__init__.py`.
- Add `init_tracker_server/app.py` with app factory/lifespan ownership or a temporary wrapper around the existing factory.
- Convert `server_app.py` to a thin compatibility shim only if focused tests prove behavior is unchanged.

Not allowed in Phase 1:

- route migrations;
- command migration;
- queue semantics changes;
- WebSocket changes;
- snapshot/cache changes;
- gameplay/combat mutation changes;
- deploy/topology changes.

### Phase 2: centralize runtime facade ownership/import boundary

Goal:

- Move the facade/contracts import boundary into the package while preserving old imports.
- Keep `server_runtime.py` as a compatibility shim during transition.
- Preserve command constants, action names, family-specific result keys, timeout/error mapping, and trace behavior.
- Keep existing route handlers and tests stable while the import owner changes.

This phase should not normalize command semantics. Normalization should be a separate task after package ownership is stable.

### Phase 3: snapshot/cache/event/WebSocket consolidation

Goal:

- Add package-owned snapshot/read-model boundary.
- Consolidate combat-lite versus tactical/map snapshot contracts.
- Define event publication and WebSocket fanout boundaries.
- Decide how long LanController-owned WebSocket state remains as an adapter behind package-owned event APIs.

This phase should be split into separate work items for snapshots and events/WebSockets unless a later task proves they can be safely handled together.

## Recommended First Implementation Slice

Recommended next work item:

- ID: `WORK-20260630-runtime-facade-package-skeleton`
- Title: Add init_tracker_server package skeleton and app factory compatibility shim
- Type: implementation

The first slice should create the package boundary without changing gameplay route behavior or command semantics.

## Acceptance Criteria For First Implementation Slice

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

## Forbidden Scope For First Implementation Slice

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

## Unknowns And Constraints

- Full WebSocket/LAN convergence remains unknown beyond the named evidence.
- Direct route inventory is intentionally incomplete; this plan is not route-migration authorization.
- Snapshot/cache migration boundaries remain future work because current `read_snapshot(...)` fails closed.
- The first implementation slice must stop if preserving `server_app.create_app(...)` requires route, queue, WebSocket, snapshot, or gameplay changes.

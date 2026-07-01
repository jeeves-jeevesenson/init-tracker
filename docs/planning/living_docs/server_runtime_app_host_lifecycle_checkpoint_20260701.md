# Server Runtime App-Host Lifecycle Checkpoint - 2026-07-01

## Status

Checkpoint/decision document only. This document does not authorize app implementation, test edits, script edits, runtime behavior changes, snapshot schema changes, response payload changes, cache TTL changes, cache ownership changes, route ownership changes, threadpool behavior changes, lifespan behavior changes, server launch command changes, route migration, browser asset edits, deploys, commits, pushes, production commands, service restarts, or SSH.

## Decision Summary

The current package boundary is strong enough to support a small app-host/runtime lifecycle implementation slice, but only if that slice preserves route bodies and legacy runtime authority.

Recommended next work item:

`WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`

The safest first implementation should introduce a package-owned host boundary for app creation and Uvicorn/thread lifecycle, while leaving legacy route registration, route bodies, snapshot builders, cache ownership, Tk polling, queue semantics, WebSocket behavior, and gameplay authority in `dnd_initative_tracker.py` / `LanController` for now.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-runtime-facade-post-offload-responsiveness-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_offload_responsiveness_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/agent_tasks/templates/task-packet.md`

Code inspected:

- `init_tracker_server/app.py`
- `init_tracker_server/runtime.py`
- `server_app.py`
- `serve_headless.py`
- `server_runtime.py`
- `dnd_initative_tracker.py`, limited to app creation, route registration evidence, `LanController.start()`, server startup/shutdown, snapshot warm-up, Uvicorn/thread ownership, runtime attachment/seeding, route-local DM combat snapshot offload helper, and DM-console snapshot cache sections.

No app code, tests, scripts, browser assets, old plans, old bug reports, runtime reports, `majorTODO.md`, broad repo grep, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## Lifecycle Ownership Map

### FastAPI app creation

Current owner: `init_tracker_server.app.create_app(...)`.

`create_app(lan_controller=None)` constructs `FastAPI(lifespan=app_lifespan)`, initializes `app.state.ready`, `app.state.lan_controller`, and `app.state.runtime`, then returns the app. The package app factory imports `ServerRuntimeFacade` through `init_tracker_server.runtime`.

Legacy host path: `LanController.start()` imports `create_app` through the `server_app.py` compatibility shim and calls `create_app(lan_controller=self)`.

Compatibility shim: `server_app.py` only re-exports `app_lifespan` and `create_app` from `init_tracker_server.app`.

### Route registration

Current owner for health/readiness routes: `init_tracker_server.app`.

Current owner for LAN, DM, player, static, WebSocket, gameplay, map, shop, character, admin, and remaining API routes: `LanController.start()` in `dnd_initative_tracker.py`.

`LanController.start()` mounts static assets on `self._fastapi_app`, defines middleware on that app, then registers the large nested route set directly through decorators such as `@self._fastapi_app.get(...)`, `@self._fastapi_app.post(...)`, `@self._fastapi_app.delete(...)`, and `@self._fastapi_app.websocket(...)`. Route bodies and most route-local helper closures remain in the legacy script path.

### Health/readiness wiring

Current owner: `init_tracker_server.app`.

`app_lifespan(app)` calls `app.state.runtime.start()` if present, sets `app.state.ready = True`, then on shutdown sets `app.state.ready = False` and calls `app.state.runtime.shutdown()` if present.

`create_app(...)` registers:

- `GET /health`
- `GET /api/health`
- `GET /ready`
- `GET /api/ready`

Current readiness semantics remain simple app-state readiness plus the thin runtime facade readiness flag.

### Runtime facade attachment and `app.state.runtime`

Current owner for attachment: `init_tracker_server.app.create_app(...)`.

Current facade implementation source: `server_runtime.py`.

Current package import boundary: `init_tracker_server.runtime`, which re-exports `ServerRuntimeFacade`, command/status constants, and command/snapshot/trace contracts from `server_runtime.py`.

`create_app(...)` creates `ServerRuntimeFacade(lan_controller=lan_controller)` and assigns it to `app.state.runtime`. `LanController.start()` then mirrors that reference into `self._runtime = self._fastapi_app.state.runtime`.

`ServerRuntimeFacade.start()` and `shutdown()` only toggle the facade `_ready` flag. They do not own Uvicorn, threads, queues, snapshot caches, WebSocket clients, or tracker shutdown.

### Snapshot warm-up and initial snapshot seeding

Current owner: legacy `LanController.start()` and legacy tracker broadcast/snapshot paths.

Immediately before starting Uvicorn, `LanController.start()` seeds:

- `self._cached_snapshot = self.app._lan_snapshot(include_static=True, hydrate_static=True)`
- `self._cached_pcs = list(self.app._lan_pcs() ... else self.app._lan_claimable())`

If static hydration fails, it falls back to `self.app._lan_snapshot(include_static=False, hydrate_static=False)`.

DM-console snapshot caching remains legacy-owned. `LanController._dm_console_snapshot(...)` uses a short-lived `_cached_dm_snapshot` only when the include-tactical mode matches. The broadcast path prebuilds a DM-console payload through `_dm_console_snapshot_payload(...)`, then writes `_cached_dm_snapshot`, `_cached_dm_snapshot_at`, and `_cached_dm_snapshot_include_tactical` so same-request route handlers can avoid rebuilding the snapshot.

No snapshot warm-up or DM-console cache ownership currently lives in `init_tracker_server`.

### Uvicorn startup, server thread creation, and shutdown

Current owner: `LanController.start()` and `LanController.stop()`.

`LanController.start()` lazily imports FastAPI and Uvicorn dependencies, creates a fresh event loop inside a nested `run_server()` function, builds `uvicorn.Config(self._fastapi_app, host=self.cfg.host, port=self.cfg.port, log_level="warning", access_log=False)`, creates `uvicorn.Server(config)`, stores it in `self._uvicorn_server`, runs `server.serve()`, then starts a daemon thread named `InitTrackerLAN`.

`LanController.stop()` currently requests shutdown by setting `self._uvicorn_server.should_exit = True` and logging. It does not own a package-level host object, join policy, cancellation model, or graceful shutdown contract beyond the existing Uvicorn flag.

`serve_headless.py` is a compatibility launcher. It sets `INIT_TRACKER_HEADLESS=1`, imports `dnd_initative_tracker`, constructs `InitiativeTracker()`, optionally avoids LAN auto-start, then enters `app.mainloop()`. Its shutdown helper calls `lan.stop()` and `app.quit()`. It is not the ASGI app or Uvicorn lifecycle owner.

### What still belongs to `dnd_initative_tracker.py` / `LanController.start()`

These concerns still live in the legacy script/runtime host path:

- Lazy FastAPI route dependency imports used by nested route handlers.
- Package app invocation through the `server_app.py` shim.
- `self._fastapi_app` and `self._runtime` mirroring.
- Request path/debug middleware.
- Static asset mounts.
- Route registration for the large LAN/DM/player/admin/map/shop/character/WebSocket route set.
- Route bodies and route-local closure helpers.
- `GET /api/dm/combat` route-local threadpool offload and tactical serialization via `_dm_combat_read_snapshot_in_threadpool(...)`.
- Initial LAN snapshot and player-list seeding.
- Uvicorn config, server object, event loop creation, daemon server thread, and stop flag behavior.
- Tk polling startup through `self.app.after(60, self._tick)`.
- DM-console snapshot builders, tactical snapshot builders, LAN snapshot builders, short-lived DM snapshot cache, queue state, WebSocket clients, and gameplay authority.

## Minimal Implementation Decision

Proceed next only with `WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`.

The first implementation should move canonical host ownership, not route ownership.

Recommended target shape:

- Add a package-owned host boundary, likely `init_tracker_server/host.py`.
- Let that host boundary create the app through `init_tracker_server.app.create_app(lan_controller=...)`.
- Let that host boundary own Uvicorn config creation, Uvicorn server storage, event loop creation, daemon thread creation, and stop-by-`should_exit` behavior.
- Keep `LanController.start()` responsible for registering the existing routes against the package-created app.
- Keep existing route bodies nested/legacy-owned for this slice unless the implementation needs a small helper extraction purely to pass the existing app into the registration block.
- Keep the existing `self._fastapi_app`, `self._runtime`, `self._uvicorn_server`, `self._loop`, and `self._server_thread` compatibility attributes populated.
- Keep initial `_cached_snapshot` / `_cached_pcs` seeding in `LanController.start()`.
- Keep `LanController.stop()` externally compatible, delegating to the package host if present while preserving the existing `server.should_exit = True` behavior.

This is small enough because app creation is already package-owned and the remaining Uvicorn/thread setup is isolated at the end of `LanController.start()`. It is safe only if route registration and legacy runtime authority remain unchanged.

## Required Preservation For The Future Slice

The implementation must explicitly preserve:

- Existing route paths, methods, route bodies, response payloads, and HTTP status mappings.
- `server_app.create_app` and `server_app.app_lifespan` compatibility.
- `app.state.ready`, `app.state.lan_controller`, and `app.state.runtime` initialization.
- Lifespan behavior: runtime start before readiness true, readiness false before runtime shutdown.
- `ServerRuntimeFacade.start()`, `shutdown()`, `is_ready()`, `submit_command(...)`, and `read_snapshot(...)` semantics.
- `LanController._runtime` pointing at the same object as `app.state.runtime`.
- `GET /api/dm/combat` route-local `run_in_threadpool` behavior and tactical-read serialization.
- Existing snapshot warm-up and DM-console short-lived cache behavior.
- Uvicorn host, port, log level, access log setting, thread name, daemon setting, and stop flag behavior.
- Tk polling startup timing.
- Headless launcher behavior and CLI flags.
- Queue command behavior, action-state polling, timeout/error mapping, trace names, WebSocket fanout, and claims/auth behavior.

## Future Validation Plan

For the minimal implementation slice, use bounded validation only:

- `timeout 10s python3 -m py_compile init_tracker_server/app.py init_tracker_server/runtime.py init_tracker_server/host.py server_app.py serve_headless.py server_runtime.py dnd_initative_tracker.py`
- `timeout 30s python3 -m unittest tests/test_server_health.py`
- `timeout 120s python3 -m unittest tests/test_headless_host.py`
- `timeout 60s python3 -m unittest tests/test_server_runtime.py`
- `timeout 10s git diff --check`
- `git status --short`

Developer smoke should remain separate if requested. A good smoke target after implementation would be startup plus `/health`, `/api/health`, `/ready`, `/api/ready`, `/dm`, `/api/dm/combat`, and `/api/dm/combat?workspace=dmcontrol`, but browser smoke is not replaced by Python tests.

## Deferred Scope

Deferred until after minimal package host ownership is proven:

- Moving route modules into `init_tracker_server/routes/`.
- Moving route bodies out of `LanController.start()`.
- Changing health/readiness payloads or readiness semantics.
- Changing lifespan behavior beyond existing runtime start/shutdown calls.
- Changing server launch commands or `serve_headless.py` CLI behavior.
- Adding shutdown join/cancellation semantics.
- Changing snapshot schemas, response payloads, cache TTLs, cache ownership, or static hydration.
- Moving snapshot warm-up into the package host.
- Broadening `run_in_threadpool` usage.
- Lower-level `_dm_tactical_snapshot()` or `_lan_snapshot()` offload.
- Static tactical/map queue migration.
- Queue-wait behavior changes.
- Async command acceptance semantics.
- Player-command routes.
- Combat mutation routes.
- Rules-aware movement, AoE creation, structures, ships, boarding links, or other high-risk gameplay work.
- WebSocket behavior, claims/auth behavior, hidden-information handling, reconnect behavior, or persistence behavior changes.
- Production operations, commits, pushes, deploys, service restarts, SSH, DNS, or topology changes.

## Why Not Route Migration Now

The named files show route registration is still deeply intertwined with local closures, static assets, auth helpers, WebSocket state, runtime references, DM snapshot helpers, and legacy tracker state. Moving route bodies in the same slice as host ownership would mix lifecycle risk with route behavior risk.

The safer migration order is:

1. Move app/server host lifecycle ownership into a package boundary while route registration remains legacy-owned.
2. Prove startup, readiness, shutdown request, headless host, runtime facade attachment, and key route behavior remain stable.
3. Only then consider route extraction or deeper runtime-service ownership in separately authorized work.

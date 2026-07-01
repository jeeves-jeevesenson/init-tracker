# WORK-20260701-app-host-runtime-lifecycle-checkpoint

Status: Completed

## Goal

Map what still lives in the legacy script/runtime host path versus the `init_tracker_server` package boundary, then decide the safest minimal implementation slice for app-host/runtime lifecycle realignment.

This was a docs/planning checkpoint only. No app code, tests, scripts, runtime behavior, route bodies, server launch commands, lifespan behavior, snapshot schemas, response payloads, cache TTLs, cache ownership, route ownership, threadpool behavior, queue behavior, command semantics, WebSocket behavior, browser assets, deploys, commits, pushes, or production commands were changed or run.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-runtime-facade-post-offload-responsiveness-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_offload_responsiveness_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/agent_tasks/templates/task-packet.md`
- `init_tracker_server/app.py`
- `init_tracker_server/runtime.py`
- `server_app.py`
- `serve_headless.py`
- `server_runtime.py`
- `dnd_initative_tracker.py`, limited to app creation, route registration evidence, `LanController.start()`, server startup/shutdown, snapshot warm-up, Uvicorn/thread ownership, runtime attachment/seeding, route-local DM combat snapshot offload helper, and DM-console snapshot cache sections.

No app source outside the named files, tests, scripts, old plans, old bug reports, runtime reports, `majorTODO.md`, broad repo history, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_checkpoint_20260701.md`

No active work item copy was left after completion.

## Lifecycle Ownership Map

FastAPI app creation is package-owned by `init_tracker_server.app.create_app(...)`. `server_app.py` is only a compatibility shim that re-exports `app_lifespan` and `create_app`.

Health/readiness wiring is package-owned by `init_tracker_server.app`: the app factory registers `/health`, `/api/health`, `/ready`, and `/api/ready`, and `app_lifespan(...)` toggles `app.state.ready` while calling `runtime.start()` and `runtime.shutdown()`.

Runtime facade attachment is package-owned at the app-state boundary: `create_app(...)` creates `ServerRuntimeFacade(lan_controller=lan_controller)` through `init_tracker_server.runtime` and assigns it to `app.state.runtime`. The facade implementation still lives in `server_runtime.py`, and `init_tracker_server.runtime` remains a re-export/import boundary. `LanController.start()` mirrors the attached runtime into `self._runtime`.

Route registration is still legacy-owned. `LanController.start()` mounts static assets, defines middleware, and registers the large LAN/DM/player/admin/map/shop/character/WebSocket route set directly against `self._fastapi_app`. Route bodies and most route-local closure helpers remain in `dnd_initative_tracker.py`.

Snapshot warm-up and initial snapshot seeding are still legacy-owned. `LanController.start()` seeds `_cached_snapshot` and `_cached_pcs` immediately before Uvicorn startup. DM-console short-lived cache ownership remains in `LanController._dm_console_snapshot(...)` and the legacy broadcast path that writes `_cached_dm_snapshot`, `_cached_dm_snapshot_at`, and `_cached_dm_snapshot_include_tactical`.

Uvicorn startup, event loop creation, server thread creation, and shutdown request behavior are still legacy-owned by `LanController.start()` and `LanController.stop()`. `serve_headless.py` remains a compatibility launcher around `InitiativeTracker()` and `LanController.stop()`, not an ASGI host owner.

`ServerRuntimeFacade.start()` and `shutdown()` are intentionally thin readiness toggles only. They do not own Uvicorn, threads, queues, snapshots, WebSockets, or tracker shutdown.

## Decision

Proceed next with a bounded implementation candidate:

`WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`

The implementation should move canonical app/server host ownership into a package-owned host boundary while preserving route bodies and legacy runtime authority.

Recommended target shape:

- Add a package-owned host boundary, likely `init_tracker_server/host.py`.
- Let that host create the app through `init_tracker_server.app.create_app(lan_controller=...)`.
- Let that host own Uvicorn config creation, Uvicorn server storage, event loop creation, daemon thread creation, and stop-by-`should_exit` behavior.
- Keep `LanController.start()` responsible for registering the existing routes against the package-created app.
- Keep existing route bodies nested/legacy-owned for this slice unless the implementation needs a small helper extraction purely to pass the app into the registration block.
- Keep compatibility attributes populated: `self._fastapi_app`, `self._runtime`, `self._uvicorn_server`, `self._loop`, and `self._server_thread`.
- Keep initial `_cached_snapshot` / `_cached_pcs` seeding in `LanController.start()`.
- Keep `LanController.stop()` externally compatible, delegating to the package host if present while preserving the current `server.should_exit = True` shutdown request behavior.

## Explicit Preservation For Next Slice

The next implementation must preserve existing route paths, route methods, route bodies, response payloads, HTTP status mappings, health/readiness payloads, lifespan semantics, `server_app` compatibility, `app.state.*` initialization, runtime facade semantics, route-local DM combat snapshot offload and tactical serialization, snapshot warm-up/cache behavior, Uvicorn config values, thread name/daemon setting, Tk polling startup, headless launcher behavior, queue command behavior, action-state polling, timeout/error mapping, trace names, WebSocket fanout, claims/auth behavior, hidden-information handling, reconnect behavior, and persistence behavior.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

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
- WebSocket behavior, claims/auth behavior, hidden-information handling, reconnect behavior, persistence behavior, browser assets, production operations, commits, pushes, deploys, service restarts, SSH, DNS, or topology changes.

## Future Validation Recommendation

For `WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`, use bounded validation:

- `timeout 10s python3 -m py_compile init_tracker_server/app.py init_tracker_server/runtime.py init_tracker_server/host.py server_app.py serve_headless.py server_runtime.py dnd_initative_tracker.py`
- `timeout 30s python3 -m unittest tests/test_server_health.py`
- `timeout 120s python3 -m unittest tests/test_headless_host.py`
- `timeout 60s python3 -m unittest tests/test_server_runtime.py`
- `timeout 10s git diff --check`
- `git status --short`

Developer smoke remains separate if requested.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle.

Allowed next action is to open:

`WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`

That next work item should be implementation, but only for the minimal package-owned app/server host boundary described above.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results are recorded in the final agent report.

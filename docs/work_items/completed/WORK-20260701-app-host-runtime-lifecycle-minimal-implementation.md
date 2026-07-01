# WORK-20260701-app-host-runtime-lifecycle-minimal-implementation

Status: Completed

## Goal

Add the smallest package-owned app/server host boundary that moves Uvicorn config/server/thread/stop-request ownership out of the legacy host path while preserving existing route bodies, route registration, launch commands, lifespan behavior, health/readiness payloads, snapshot warm-up ownership, and legacy runtime authority.

This implementation did not move route bodies, route registration, launch commands, lifespan behavior, snapshot warm-up ownership, WebSocket behavior, queue semantics, shutdown join/cancellation semantics, browser assets, gameplay routes, production topology, deploys, commits, pushes, SSH, or service restarts.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-runtime-facade-post-offload-responsiveness-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_offload_responsiveness_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/agent_tasks/templates/task-packet.md`
- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`
- `init_tracker_server/runtime.py`
- `server_app.py`
- `serve_headless.py`
- `server_runtime.py`
- `dnd_initative_tracker.py`, limited to imports, `LanController.__init__`, `LanController.start()`, Uvicorn/thread startup, snapshot warm-up adjacency, and `LanController.stop()`
- `tests/test_server_app.py`
- `tests/test_server_health.py`
- `tests/test_headless_host.py`
- `tests/test_server_runtime.py`

No `majorTODO.md`, old bug reports, runtime reports, historical notes, browser assets, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## Files Changed

- `init_tracker_server/host.py`
- `dnd_initative_tracker.py`
- `tests/test_server_host.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`

No `init_tracker_server/__init__.py`, `init_tracker_server/app.py`, `init_tracker_server/runtime.py`, `server_app.py`, `serve_headless.py`, or `server_runtime.py` code was changed.

## Host Boundary API Added

Added `init_tracker_server.host.UvicornServerHost`.

Constructor:

```python
UvicornServerHost(
    app,
    *,
    host,
    port,
    log_level="warning",
    access_log=False,
    thread_name="InitTrackerLAN",
    on_server_ready=None,
)
```

Public methods and properties:

- `start() -> threading.Thread`
- `request_stop() -> None`
- `loop`
- `server`
- `thread`

The boundary accepts an already-created and already-registered ASGI app. It does not create the app, register routes, seed snapshots, run Tk polling, join threads, cancel tasks, or own runtime/gameplay authority.

## Legacy Ownership Moved

Moved these mechanics out of the inline `LanController.start()` block and into `UvicornServerHost.start()`:

- `asyncio.new_event_loop()`
- `asyncio.set_event_loop(loop)`
- `uvicorn.Config(app, host=..., port=..., log_level="warning", access_log=False)`
- `uvicorn.Server(config)`
- `loop.run_until_complete(server.serve())`
- daemon `threading.Thread(..., name="InitTrackerLAN", daemon=True)` creation and start

Moved the canonical stop request from `LanController.stop()` to `UvicornServerHost.request_stop()`:

- `server.should_exit = True`

`LanController` keeps compatibility attributes populated through the host callback:

- `self._loop`
- `self._uvicorn_server`
- `self._server_thread`
- `self._server_host`

## Legacy Ownership Preserved

Preserved in `init_tracker_server.app`:

- FastAPI app creation through `create_app(...)`
- health/readiness route wiring
- lifespan readiness toggling
- `app.state.runtime` attachment

Preserved in `server_app.py`:

- compatibility shim behavior

Preserved in `LanController.start()` / `dnd_initative_tracker.py`:

- dependency check path and missing dependency handling
- app creation call through `server_app.create_app(lan_controller=self)`
- `self._fastapi_app` and `self._runtime` mirroring
- static mounts
- route helper closures
- all route registration and route bodies
- route-local DM-combat read offload and tactical serialization
- initial `_cached_snapshot` / `_cached_pcs` seeding
- Tk polling startup through `self.app.after(60, self._tick)`
- existing host, port, log level, access log, thread name, and daemon values
- queue state, WebSocket state, auth/claims/reconnect behavior, persistence, and gameplay authority

Preserved in `serve_headless.py`:

- existing launch command, flags, environment setup, signal handling, and shutdown call path

## Tests Added

Added `tests/test_server_host.py`.

Coverage:

- `UvicornServerHost.start()` builds Uvicorn config/server with the existing host, port, log level, and access-log values.
- `UvicornServerHost.start()` creates and sets the per-thread event loop.
- `UvicornServerHost.start()` creates a daemon thread named `InitTrackerLAN`.
- `on_server_ready` exposes the loop/server needed for legacy compatibility attributes.
- repeated `start()` reuses an existing live thread.
- `request_stop()` sets `server.should_exit = True` and tolerates a missing server.

The tests use fakes for `uvicorn`, event loop creation, and `threading.Thread`; they do not start a real server or open sockets.

## Validation

Required validation passed:

```text
git status --short
 M dnd_initative_tracker.py
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? init_tracker_server/host.py
?? logs/context/
?? tests/test_server_host.py
```

```text
timeout 30s .venv/bin/python -m py_compile init_tracker_server/app.py init_tracker_server/runtime.py init_tracker_server/host.py server_app.py serve_headless.py dnd_initative_tracker.py server_runtime.py
passed
```

```text
timeout 60s .venv/bin/python -m pytest tests/test_server_host.py
3 passed in 0.39s
```

```text
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
74 passed in 2.43s
```

Final validation after docs updates also passed:

```text
timeout 10s git diff --check
passed
```

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item. The completed table now includes this work item and the allowed next action is limited to review, developer smoke if desired, and commit. Route migration and broader runtime/gameplay work remain blocked without a new active work item.

## Remaining Risk

The focused unit tests prove the host boundary without sockets, and `tests/test_server_runtime.py` still passes. A developer smoke is recommended before commit because the changed seam affects actual LAN server startup timing and Uvicorn thread hosting, which the no-socket unit tests intentionally avoid exercising.

## Best Next Broad Pass

After review/smoke/commit, the next broad pass should be a planning/evidence checkpoint for the next app-host ownership step. Do not begin route migration, route body extraction, shutdown semantics changes, or runtime scheduling changes without a separately authorized active work item.

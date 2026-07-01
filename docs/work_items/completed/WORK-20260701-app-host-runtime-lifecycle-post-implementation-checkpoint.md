# WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint

Status: Completed

## Goal

Complete a bounded post-implementation checkpoint for `WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`.

Decide what the new `init_tracker_server.host.UvicornServerHost` boundary changed, what it intentionally preserved, what validation proved, what developer-smoke evidence is or is not available, and which remaining ownership problem is highest-value next.

This was a docs/evidence checkpoint only. No app code, tests, route registration, route bodies, runtime behavior, queue behavior, WebSocket behavior, payloads, cache ownership, TTLs, static hydration, snapshot warm-up ownership, launch commands, lifespan behavior, production topology, deploys, commits, pushes, SSH, or service restarts were changed.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_checkpoint_20260701.md`
- `init_tracker_server/host.py`
- `tests/test_server_host.py`
- `dnd_initative_tracker.py`, limited to the targeted `LanController.start()` / `LanController.stop()` seam

The completed implementation doc does not name a smoke log or debug trace path for this host-boundary slice, so no smoke/debug evidence file was available to inspect.

No old plans, `majorTODO.md`, runtime reports, historical notes, broad repo scans, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_post_implementation_checkpoint_20260701.md`

No active work item copy was left after completion.

## Decision

`UvicornServerHost` successfully moved the isolated Uvicorn config/server/thread/start-stop mechanics into `init_tracker_server.host`, while preserving the riskier legacy-owned route/runtime/gameplay surface.

Another host/lifecycle implementation slice is not justified now. The remaining high-value ownership issue is no longer Uvicorn thread mechanics; it is legacy route-registration ownership in `LanController.start()`.

Recommended next lane:

`WORK-20260701-app-host-route-registration-planning-checkpoint`

That next item should be docs/evidence only. It should map the current route-registration closure dependencies, static mounts, middleware, app-state/runtime coupling, and route-family boundaries, then decide whether a future route-registration extraction is safe. It should not move routes or route bodies.

If developer smoke for the host-boundary implementation remains unrecorded, the next planning/evidence item should treat live Uvicorn startup/readiness smoke as an evidence gap and should not recommend deploy guidance from this checkpoint alone.

## What Changed

Moved out of legacy ownership and into `init_tracker_server.host.UvicornServerHost`:

- `asyncio.new_event_loop()`
- `asyncio.set_event_loop(loop)`
- `uvicorn.Config(...)`
- `uvicorn.Server(...)`
- `loop.run_until_complete(server.serve())`
- daemon `threading.Thread(..., name="InitTrackerLAN", daemon=True)` creation and start
- canonical stop request through `request_stop()` setting `server.should_exit = True`

`LanController.start()` now delegates server hosting to `UvicornServerHost` and uses the ready callback to preserve compatibility attributes:

- `self._loop`
- `self._uvicorn_server`
- `self._server_thread`
- `self._server_host`

`LanController.stop()` now delegates the canonical stop request to `self._server_host.request_stop()` when present, while retaining the legacy fallback that sets `self._uvicorn_server.should_exit = True`.

## What Was Preserved

The implementation intentionally preserved:

- package app creation in `init_tracker_server.app.create_app(...)`
- `server_app.py` compatibility shim behavior
- health/readiness route wiring and payloads
- lifespan readiness toggling and runtime start/shutdown behavior
- `app.state.runtime` attachment and `LanController._runtime` mirroring
- route registration, route bodies, middleware definitions, route-local helper closures, and static mounts in `LanController.start()`
- route-local DM-combat read offload and tactical serialization behavior
- initial `_cached_snapshot` / `_cached_pcs` seeding in `LanController.start()`
- DM-console snapshot/cache ownership in legacy tracker paths
- Tk polling startup through `self.app.after(60, self._tick)`
- existing host, port, log level, access-log, thread-name, and daemon values
- launch commands and `serve_headless.py` behavior
- queue state, command semantics, WebSocket state, auth/claims/reconnect behavior, hidden-information handling, persistence, and gameplay authority

## Validation And Smoke Evidence

Recorded implementation validation proved the package host boundary at the no-socket unit level:

- `py_compile` passed for edited/adjacent Python files.
- `tests/test_server_host.py` passed with faked Uvicorn, event loop creation, and thread creation.
- `tests/test_server_runtime.py` passed after the implementation.
- `timeout 10s git diff --check` passed after implementation docs were updated.

`tests/test_server_host.py` proves `UvicornServerHost.start()` builds the expected Uvicorn config/server, sets the per-thread event loop, creates a daemon `InitTrackerLAN` thread, calls the ready callback, reuses an existing live thread, and sets `server.should_exit` on stop request.

Developer smoke is not recorded for this host-boundary slice in the completed implementation doc. The implementation doc instead states that developer smoke is recommended before commit because no-socket tests intentionally avoid exercising actual LAN server startup timing and Uvicorn thread hosting. Therefore this checkpoint does not claim live-server startup, readiness, route behavior, or shutdown-request behavior was smoke-proven after `UvicornServerHost`.

## Remaining Risk

The main post-slice risk is not the small host class itself. The larger ownership risk remains that `LanController.start()` still owns broad route registration, static mounts, middleware, route-local closures, route bodies, snapshot warm-up, and Tk polling adjacency.

The evidence also leaves a live-server gap: without a recorded host-boundary smoke log/debug trace, actual Uvicorn-thread startup and readiness behavior after the refactor are not proven by this checkpoint.

Shutdown join/cancellation semantics remain intentionally untouched. They should not become the next implementation target unless a separate evidence item shows a concrete failure, because changing them would increase lifecycle risk beyond the minimal host-boundary slice.

## Lane Selection

Route-registration planning checkpoint: selected. The next highest-value ownership problem is the legacy route-registration mass still embedded in `LanController.start()`. A planning/evidence item can map the dependency shape without changing routes.

Queue-wait evidence checkpoint: deferred. This host-boundary evidence does not introduce new queue-wait behavior or queue failures.

Deploy guidance: deferred. The host-boundary implementation changed startup mechanics, and no host-boundary developer smoke log/debug trace is recorded in the completed implementation doc.

No further migration work for now: not selected. The host boundary was a useful step, but route-registration ownership remains a clear blocker for the web-first package boundary.

Another host/lifecycle implementation slice: not selected. The remaining lifecycle-sensitive topics, especially shutdown join/cancellation, launch commands, lifespan behavior, and snapshot warm-up ownership, are higher-risk and were intentionally preserved.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item. The completed table now includes this checkpoint.

Allowed next action is to open `WORK-20260701-app-host-route-registration-planning-checkpoint` as docs/evidence only, or to record host-boundary developer smoke evidence if the developer chooses to do that before further planning.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results are recorded in the final agent report.

# Server Runtime App-Host Lifecycle Post-Implementation Checkpoint - 2026-07-01

## Status

Checkpoint/decision document only. This document does not authorize app implementation, test edits, script edits, route registration changes, route body movement, runtime behavior changes, snapshot schema changes, response payload changes, cache TTL changes, cache ownership changes, queue behavior changes, WebSocket behavior changes, lifespan behavior changes, server launch command changes, browser asset edits, deploys, commits, pushes, production commands, service restarts, or SSH.

## Decision Summary

`init_tracker_server.host.UvicornServerHost` is a valid minimal host-boundary step. It moved Uvicorn config/server/thread mechanics and the canonical stop request out of the inline legacy host path while preserving route registration, route bodies, app factory ownership, runtime facade semantics, snapshot warm-up/cache ownership, Tk polling, launch behavior, and gameplay/runtime authority.

No further host/lifecycle implementation slice is justified immediately. The next high-value lane should be a docs/evidence-only route-registration planning checkpoint:

`WORK-20260701-app-host-route-registration-planning-checkpoint`

That lane should decide how route registration could be separated from `LanController.start()` without moving route bodies or changing behavior.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_checkpoint_20260701.md`

Code inspected:

- `init_tracker_server/host.py`
- `tests/test_server_host.py`
- `dnd_initative_tracker.py`, limited to the targeted `LanController.start()` / `LanController.stop()` seam

The completed implementation doc does not name a smoke log or debug trace path for this host-boundary slice. No smoke/debug evidence file was available to inspect, and this checkpoint treats developer smoke as an evidence gap rather than as proof.

## What UvicornServerHost Moved

`UvicornServerHost` owns the isolated mechanics that had been inline in `LanController.start()`:

- creating a fresh event loop
- setting that event loop for the server thread
- building `uvicorn.Config`
- building `uvicorn.Server`
- storing the loop/server/thread
- running `server.serve()` on the event loop
- creating and starting the daemon `InitTrackerLAN` thread
- reusing an existing live thread on repeated `start()`
- requesting shutdown by setting `server.should_exit = True`

The callback passed from `LanController.start()` preserves legacy compatibility by writing the created loop and server back to `self._loop` and `self._uvicorn_server`. `LanController.start()` stores the returned thread in `self._server_thread`.

`LanController.stop()` now delegates to `self._server_host.request_stop()` when present and keeps the legacy fallback for `_uvicorn_server.should_exit`.

## What The Implementation Preserved

Preserved package-owned behavior:

- `init_tracker_server.app.create_app(...)` remains the app factory.
- health/readiness route registration remains in the app factory.
- lifespan readiness toggling and runtime start/shutdown calls are unchanged.
- `app.state.runtime` attachment remains package-owned.
- `server_app.py` remains a compatibility shim.

Preserved legacy-owned behavior:

- FastAPI route dependency imports and missing-dependency handling remain in `LanController.start()`.
- static mounts and middleware remain in `LanController.start()`.
- LAN, DM, player, admin, map, shop, character, gameplay, and WebSocket route registration remain in `LanController.start()`.
- route bodies and route-local closure helpers remain in `dnd_initative_tracker.py`.
- route-local DM-combat read offload and tactical serialization remain unchanged.
- initial `_cached_snapshot` and `_cached_pcs` seeding remain in `LanController.start()`.
- DM-console snapshot/cache ownership remains in legacy tracker paths.
- Tk polling startup remains after server-host startup.
- launch commands, headless behavior, Uvicorn config values, thread name, and daemon setting are preserved.
- queue state, command semantics, WebSocket fanout, auth/claims/reconnect, hidden-information handling, persistence, and gameplay authority are preserved.

## Validation And Smoke Reading

Recorded validation from the implementation proves the host class contract without opening sockets:

- `py_compile` passed for the edited and adjacent Python files recorded by the implementation doc.
- `tests/test_server_host.py` passed and uses fakes for Uvicorn, event loop creation, and thread creation.
- `tests/test_server_runtime.py` passed after the implementation.
- final `timeout 10s git diff --check` passed after implementation docs were updated.

The no-socket tests prove construction/delegation mechanics, not end-to-end server behavior. They do not prove actual Uvicorn startup, readiness endpoints, route serving, thread timing under real Uvicorn, or runtime shutdown behavior in a live process.

No developer-smoke proof is recorded for this host-boundary slice. The implementation doc says developer smoke is recommended before commit because the changed seam affects actual LAN server startup timing and Uvicorn thread hosting.

## Remaining Risk

The highest-value ownership problem left by this slice is route registration. `LanController.start()` still combines dependency checks, app creation through the shim, middleware, static mounts, broad route registration, nested route bodies, route-local helpers, snapshot warm-up adjacency, host startup delegation, and Tk polling startup.

Because route registration is still entangled with local closures and legacy tracker state, immediate route movement would mix behavior risk with ownership migration. The next safe step is evidence/planning, not route implementation.

The smoke gap matters for deployment decisions. Without a recorded host-boundary smoke log/debug trace, this checkpoint cannot recommend deploy guidance based on live startup/readiness proof.

## Next Lane Decision

Selected:

`WORK-20260701-app-host-route-registration-planning-checkpoint`

Purpose:

Map the current route-registration ownership in `LanController.start()`, identify closure/helper/static/middleware dependencies, separate route-registration concerns from route-body concerns, and decide whether a future minimal extraction is safe.

Constraints for the next item:

- docs/evidence only
- no route body movement
- no route registration changes
- no payload, schema, cache, queue, WebSocket, auth, gameplay, launch, lifespan, or topology changes
- no production operations
- do not claim host-boundary smoke proof unless a concrete smoke log/debug trace is provided

Deferred:

- queue-wait evidence, because this slice did not change queue behavior
- deploy guidance, because host-boundary developer smoke is not recorded
- another host/lifecycle implementation slice, because the remaining lifecycle topics are higher-risk than route-registration planning
- no-further-migration, because route-registration ownership remains a clear package-boundary blocker

## Exact Recommended Work Item

`WORK-20260701-app-host-route-registration-planning-checkpoint`

Recommended goal:

Complete a docs/evidence-only checkpoint that maps `LanController.start()` route-registration ownership after `UvicornServerHost`, identifies the minimal future route-registration extraction boundary if one is safe, and explicitly separates route-registration movement from route-body movement, gameplay behavior, payloads, cache ownership, queue behavior, WebSocket behavior, auth/claims/reconnect, launch commands, lifespan behavior, production topology, and deploy guidance.

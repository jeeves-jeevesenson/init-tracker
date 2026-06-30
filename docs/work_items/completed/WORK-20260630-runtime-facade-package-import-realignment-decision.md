# WORK-20260630-runtime-facade-package-import-realignment-decision: Runtime facade package import realignment decision

## Status

Completed docs-only decision slice.

## Type

Bounded planning/documentation pass.

## Goal

Open the next durable package-boundary decision slice for package-internal import realignment. The decision authorizes a later implementation task to make `init_tracker_server/app.py` import `ServerRuntimeFacade` through `init_tracker_server.runtime` instead of directly from `server_runtime.py`, while keeping `server_runtime.py` as the implementation source.

No implementation change was made in this pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `init_tracker_server/runtime.py`
- `init_tracker_server/app.py`
- `docs/agent_tasks/templates/task-packet.md`

## Current Status

- The `init_tracker_server/` package skeleton exists.
- `server_app.py` remains the compatibility shim.
- `init_tracker_server/runtime.py` exists as the package runtime re-export boundary.
- `server_runtime.py` remains the runtime implementation source.
- `init_tracker_server/app.py` still imports `ServerRuntimeFacade` directly from `server_runtime.py`.

## Decision

Approved minimal package-internal import realignment.

The next implementation slice should update only `init_tracker_server/app.py` so it imports `ServerRuntimeFacade` from `init_tracker_server.runtime`, preserving `server_runtime.py` as the implementation source.

## Later Implementation Boundary

Allowed:

- Update only the package-internal import path.
- Preserve public compatibility.
- Keep `server_runtime.py` as the implementation source.
- Preserve app factory, lifespan, health/readiness, and app-state runtime initialization behavior.

Not allowed:

- No snapshot implementation.
- No direct-route migration.
- No route offload.
- No instrumentation change.
- No queue, WebSocket, route, gameplay, deployment, topology, or production operation change.

## Expected Validation For Later Implementation Slice

- `timeout 10s git diff --check`
- Scoped import/app-factory validation.
- Focused server runtime tests only if already used by the existing runtime boundary work item or if the implementation slice changes the runtime re-export surface.

## Next Action

Open implementation task `WORK-20260630-runtime-facade-package-import-realignment`.

Exact task:

Update only `init_tracker_server/app.py` so `ServerRuntimeFacade` is imported from `init_tracker_server.runtime` instead of `server_runtime.py`, preserving `server_runtime.py` as the implementation source and preserving current app factory, lifespan, health/readiness, compatibility shim, route, queue, snapshot, WebSocket, and gameplay behavior.

After that implementation slice, proceed to snapshot-boundary checkpoint/planning.

## Validation For This Planning Pass

Required validation:

- `git status --short`
- `timeout 10s git diff --check`

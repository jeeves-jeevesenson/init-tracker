# Server Runtime Package Import Realignment Decision - 2026-06-30

## Status

Decision document. This document authorizes a later implementation slice; it does not implement the import change.

No app, runtime, route, queue, snapshot, WebSocket, test, deployment, topology, port, service, browser smoke, or production operation change is authorized by this document.

## Current Status

- The `init_tracker_server/` package skeleton exists.
- `server_app.py` remains the compatibility shim for existing `create_app(...)` imports.
- `init_tracker_server/runtime.py` exists as the package runtime re-export boundary.
- `server_runtime.py` remains the implementation source for `ServerRuntimeFacade`, runtime command contracts, status constants, command constants, snapshot contracts, and trace contracts.
- `init_tracker_server/app.py` still imports `ServerRuntimeFacade` directly from `server_runtime.py`.

## Decision

Approve a minimal package-internal import realignment.

The next implementation slice should update `init_tracker_server/app.py` to import `ServerRuntimeFacade` through `init_tracker_server.runtime` instead of directly from `server_runtime.py`.

Rationale:

- The package runtime re-export boundary now exists and is proven by the completed runtime re-export work item.
- Package-owned app code should consume the package-owned runtime boundary instead of reaching around it to the legacy implementation module.
- This is a narrow boundary realignment only. It should not move implementation code, normalize command semantics, or change runtime behavior.
- Keeping `server_runtime.py` as the implementation source preserves existing public compatibility while allowing package-internal imports to converge on the durable boundary.

## Implementation Boundary For Later Slice

Allowed:

- Update only the package-internal import path in `init_tracker_server/app.py`.
- Preserve public compatibility for `server_app.py`, `server_runtime.py`, and existing callers.
- Keep `server_runtime.py` as the implementation source.
- Preserve existing health/readiness behavior and app-state initialization semantics.
- Preserve `app.state.runtime = ServerRuntimeFacade(lan_controller=lan_controller)` behavior, with `ServerRuntimeFacade` resolved through `init_tracker_server.runtime`.

Not allowed:

- No snapshot implementation.
- No snapshot/cache movement.
- No direct-route migration.
- No route offload.
- No instrumentation change.
- No command normalization.
- No command constant, action-name, result-key, timeout/error, or trace-event rename.
- No queue adapter change.
- No WebSocket/event change.
- No gameplay/combat/map mutation change.
- No launcher, deployment, topology, port, service, or production operation change.

## Validation Expected For Later Implementation Slice

Required:

- `timeout 10s git diff --check`
- Scoped import/app-factory validation proving `init_tracker_server.app.create_app(...)` still constructs a FastAPI app, initializes `app.state.runtime`, and preserves health/readiness behavior.

Conditional:

- Run focused server runtime tests only if they are already used by the existing runtime boundary work item or if the implementation slice changes the runtime re-export surface. The expected import-only slice should not need broad test expansion.

Do not run full test suites. Do not run browser smoke.

## Next Action

Open implementation task `WORK-20260630-runtime-facade-package-import-realignment`.

Exact implementation task:

Update only `init_tracker_server/app.py` so `ServerRuntimeFacade` is imported from `init_tracker_server.runtime` instead of `server_runtime.py`, preserving `server_runtime.py` as the implementation source and preserving current app factory, lifespan, health/readiness, compatibility shim, route, queue, snapshot, WebSocket, and gameplay behavior.

After the implementation slice passes scoped validation, proceed to a snapshot-boundary checkpoint/planning pass.

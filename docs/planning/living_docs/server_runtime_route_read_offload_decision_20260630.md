# Server Runtime Route Read Offload Decision - 2026-06-30

## Status

Decision document only. This document does not authorize app implementation, tests, route migration, cache behavior changes, TTL changes, snapshot schema changes, queue behavior changes, LAN controller changes, Tk behavior changes, WebSocket changes, gameplay changes, browser asset edits, server starts, deploys, commits, pushes, or production commands.

## Decision Summary

Route-side read offload is justified now, but only as a narrow transition mitigation for the DM-console read route.

The next implementation candidate is:

`WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation`

The implementation should offload only the `GET /api/dm/combat` route's call to `ServerRuntimeFacade.read_snapshot(dm_console)`. It should not make the facade globally asynchronous, should not offload all snapshot modes, and should not move threadpool execution into `_dm_tactical_snapshot()` or `_lan_snapshot()`.

The success criterion is event-loop responsiveness: health/readiness should not spike in lockstep with slow DM-console workspace reads. The first offload slice is not expected to make tactical/LAN snapshot construction itself cheaper.

## Evidence Inspected

Documents:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_smoke_latency_read_model_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`

Code sections:

- `scripts/server_responsiveness_harness.py`
- `dnd_initative_tracker.py`: `GET /api/dm/combat`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_lan_snapshot()`, and LAN broadcast DM-console prebuild/cache assignment.
- `server_runtime.py`: `ServerRuntimeFacade.read_snapshot()` and adjacent DM-console snapshot validation/dispatch.

Logs inspected with `grep`, `head`, `tail`, and `sed` only:

- `logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_20260630-204930.jsonl`
- `logs/debug-trace-20260630-204822.jsonl`

## Harness Finding

The valid harness run lasted 60 seconds with 0.5 second polling intervals. It produced 120 rounds and 720 sample records across:

- `/health`
- `/api/health`
- `/ready`
- `/api/ready`
- `/api/dm/combat`
- `/api/dm/combat?workspace=dmcontrol`

There were no failures and every sample returned HTTP 200.

The median latencies were low, around `12-16 ms`, but p95/max latencies spiked across all endpoints:

- `/health`: p50 `12.324 ms`, p95 `898.975 ms`, max `976.759 ms`.
- `/api/health`: p50 `14.345 ms`, p95 `897.679 ms`, max `976.826 ms`.
- `/ready`: p50 `16.512 ms`, p95 `896.786 ms`, max `977.464 ms`.
- `/api/ready`: p50 `13.757 ms`, p95 `897.209 ms`, max `976.381 ms`.
- `/api/dm/combat`: p50 `13.184 ms`, p95 `898.410 ms`, max `977.185 ms`.
- `/api/dm/combat?workspace=dmcontrol`: p50 `12.698 ms`, p95 `890.811 ms`, max `976.909 ms`.

The spikes are shared by whole concurrent polling rounds. This means the concern is server responsiveness while heavier read work overlaps, not only the user-facing latency of the DM combat endpoint itself.

## Debug Trace Finding

The trace identifies `GET /api/dm/combat?workspace` as the route-context slow read path.

Examples:

- A workspace combat read returned HTTP 200 in about `884.889 ms`, with `_dm_console_snapshot` about `881.641 ms`, `_dm_console_snapshot_payload` about `881.193 ms`, `_dm_tactical_snapshot` about `880.205 ms`, and `_lan_snapshot` about `879.776 ms`.
- Another workspace combat read returned HTTP 200 in about `624.684 ms`, with `_dm_console_snapshot` about `622.585 ms`, `_dm_console_snapshot_payload` about `622.248 ms`, `_dm_tactical_snapshot` about `621.381 ms`, and `_lan_snapshot` about `620.947 ms`.
- A late workspace read returned HTTP 200 in about `2.712 ms`, with `_dm_console_snapshot` about `1.113 ms`, `_dm_console_snapshot_payload` about `0.924 ms`, `_dm_tactical_snapshot` about `0.414 ms`, and `_lan_snapshot` about `0.214 ms`.

The route can be fast when the current path is cheap or cache-assisted, but its slow outliers are dominated by the tactical/LAN snapshot chain.

The trace also contains 56 standalone `_lan_snapshot` slow spans and one `_lan_snapshot` hang candidate around `24474.390 ms`. This is important residual risk: route-side offload can protect the event loop from the route read path, but it does not make every standalone LAN snapshot safe or cheap.

## Code Boundary Finding

`GET /api/dm/combat` already delegates through:

`ServerRuntimeFacade.read_snapshot(RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": ...}))`

The route still owns:

- DM auth check.
- DM service availability check.
- Request-context tactical preference resolution.
- HTTP error mapping.

`ServerRuntimeFacade.read_snapshot(dm_console)` synchronously delegates to:

`LanController._dm_console_snapshot(include_tactical=<explicit bool>)`

When tactical data is requested, `_dm_console_snapshot_payload()` calls the tracker app's `_dm_tactical_snapshot()`, which calls `_lan_snapshot(include_static=False, hydrate_static=False)`.

The smallest useful offload seam is therefore the existing route call to `self._runtime.read_snapshot(snap_req)`.

## Why Not Offload Lower

Do not offload `_dm_tactical_snapshot()` or `_lan_snapshot()` first.

Reasons:

- `_lan_snapshot()` reads and mutates legacy tracker/LAN state while constructing a payload.
- It can interact with `_map_window` and Tk-owned objects when a desktop map window exists.
- It updates local LAN state such as positions, AoEs, obstacle/terrain mirrors, canonical map state, and cache-related fields.
- Lower-level offload would affect route, WebSocket, broadcast, and possibly desktop contexts at once.
- The first evidence-backed problem is event-loop responsiveness for route-context reads, not a proven safe threading model for every LAN snapshot caller.

## Why Not Global Facade Offload

Do not make `ServerRuntimeFacade.read_snapshot()` globally async/offloaded in the first implementation.

Reasons:

- Combat-only reads do not show the same heavy tactical/LAN cost.
- Tactical mode and future snapshot modes may need different thread-safety constraints.
- A global facade executor would become new runtime ownership and would need its own cancellation, timeout, saturation, and trace contract.
- The route already has the request context needed to resolve tactical inclusion before offload.

## First Implementation Shape

The next implementation should:

- Keep `GET /api/dm/combat` as the only production route changed.
- Keep route auth and `_dm_service` readiness checks before offload.
- Build `RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": <bool>})` before offload.
- Offload only the synchronous `self._runtime.read_snapshot(snap_req)` call.
- Preserve the current success response shape by returning `result.data`.
- Preserve current fail-closed mappings: `runtime_not_ready` to HTTP 503, other unsuccessful results to HTTP 500, unexpected exceptions to generic HTTP 500.
- Avoid passing the FastAPI `Request` object or auth token into the worker.
- Avoid cache TTL, cache ownership, snapshot schema, queue, WebSocket, gameplay, or topology changes.

If the implementation needs a concurrency guard, it should be narrow to DM-console read offload and should not become a broad runtime executor contract without a new decision.

## Correctness Risks To Carry Into Implementation

- Legacy tracker state may race under threadpool execution.
- Tk map-window access is unsafe from worker threads unless proven absent or protected in the validated mode.
- One-shot DM snapshot cache fields may race with concurrent reads or LAN broadcast prebuild.
- Request context may not propagate to the worker, so `include_tactical` must remain explicit.
- Trace context may not propagate perfectly across the threadpool boundary.
- Worker work may continue after client disconnect if cancellation is not handled.
- Offload can saturate the worker pool under repeated polling if concurrency is unbounded.
- Route offload will not fix standalone `_lan_snapshot` slow spans or startup YAML/cache work.

## Validation Required For Implementation

Required focused commands:

```bash
git status --short
timeout 10s git diff --check
timeout 10s .venv/bin/python -m py_compile dnd_initative_tracker.py server_runtime.py tests/test_server_runtime.py
timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q
```

Required focused test assertions if tests are touched:

- The route still calls `read_snapshot(dm_console)`.
- `include_tactical` is explicit before offload.
- Auth failure does not enqueue/offload snapshot work.
- `runtime_not_ready` still maps to HTTP 503.
- Other failed snapshot results still map to HTTP 500.
- Worker exceptions still fail closed.
- The FastAPI `Request` object is not passed into worker execution.

Required developer smoke/evidence:

- Headless server smoke with debugging enabled.
- DM console and DM control/workspace load.
- LAN claim smoke.
- `GET /api/dm/combat` and `GET /api/dm/combat?workspace=dmcontrol` return HTTP 200.
- `scripts/server_responsiveness_harness.py --host 127.0.0.1 --port 8787 --duration-seconds 60 --interval-seconds 0.5 --timeout-seconds 2` runs while heavier DM read-model activity is occurring.
- Harness evidence shows health/readiness no longer spike in lockstep with slow DM-console route reads.
- Debug trace preserves enough route/snapshot spans to identify whether any remaining spikes come from standalone `_lan_snapshot` work.

## Deferred Scope

Deferred:

- Any implementation in this decision pass.
- Global read offload.
- Async `ServerRuntimeFacade.read_snapshot()` contract change.
- Offload for all snapshot types.
- `_dm_tactical_snapshot()` or `_lan_snapshot()` internal threadpool work.
- Tk/main-thread marshalling design.
- Cache TTL or ownership changes.
- Facade-owned snapshot/read-model cache.
- Static hydration changes.
- Snapshot schema or response shape changes.
- Queue behavior changes.
- WebSocket behavior changes.
- LAN controller behavior changes.
- Gameplay/combat behavior changes.
- More route adoption.
- Direct gameplay route migration.
- Player-command routes.
- Combat mutation routes.
- Rules-aware move, AoE create, structures, ships, and boarding links.
- App-host/package topology work.
- Launcher, deploy, production, commit, or push work.


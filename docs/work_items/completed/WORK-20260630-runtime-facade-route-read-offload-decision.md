# WORK-20260630-runtime-facade-route-read-offload-decision

Status: Completed

## Goal

Complete a bounded docs/evidence decision using the server responsiveness harness evidence from `WORK-20260630-runtime-facade-server-responsiveness-evidence-harness`.

Decide whether route-side read offload is justified now, whether the evidence identifies the first read path to offload, the smallest safe implementation slice if any, correctness risks, required validation and developer smoke, and deferred scope.

No app code, tests, routes, cache behavior, TTLs, snapshot schemas, queue behavior, LAN controller behavior, Tk behavior, WebSockets, gameplay behavior, app-host lifecycle, launcher behavior, production topology, deploy files, commits, or pushes were changed.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-offload-decision.md`
- `docs/planning/living_docs/server_runtime_route_read_offload_decision_20260630.md`

Removed the active work item copy after completion:

- `docs/work_items/active/WORK-20260630-runtime-facade-route-read-offload-decision.md`

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

Source sections:

- `scripts/server_responsiveness_harness.py`
- `dnd_initative_tracker.py`: `GET /api/dm/combat`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_lan_snapshot()`, and the DM-console prebuild/cache assignment in the LAN broadcast path only.
- `server_runtime.py`: `ServerRuntimeFacade.read_snapshot()` and adjacent DM-console snapshot parameter validation/dispatch only.

Logs inspected with `grep`, `head`, `tail`, and `sed` only:

- `logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_20260630-204930.jsonl`
- `logs/debug-trace-20260630-204822.jsonl`

`init_tracker_server/app.py` was not inspected because the named route/runtime sections were sufficient for this decision.

## Decision

Route-side read offload is justified now as a narrow transition mitigation for the DM-console read route.

The evidence does not justify a broad read executor, a facade-owned cache, tactical builder refactoring, lower-level `_lan_snapshot()` offload, or any cache/schema/queue behavior change. The objective of the first implementation should be to keep the ASGI event loop responsive while the existing DM-console snapshot builder runs, not to make the snapshot builder cheaper.

Selected next work item candidate:

`WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation`

## Evidence Basis

The valid harness run produced 120 samples per endpoint, 720 total samples, 0 failures, HTTP 200 throughout, and shared p95/max spikes across every endpoint:

- `/health`: p50 `12.324 ms`, p95 `898.975 ms`, max `976.759 ms`.
- `/api/health`: p50 `14.345 ms`, p95 `897.679 ms`, max `976.826 ms`.
- `/ready`: p50 `16.512 ms`, p95 `896.786 ms`, max `977.464 ms`.
- `/api/ready`: p50 `13.757 ms`, p95 `897.209 ms`, max `976.381 ms`.
- `/api/dm/combat`: p50 `13.184 ms`, p95 `898.410 ms`, max `977.185 ms`.
- `/api/dm/combat?workspace=dmcontrol`: p50 `12.698 ms`, p95 `890.811 ms`, max `976.909 ms`.

The shared spikes are visible in whole polling rounds. For example, round 1 had all six endpoint samples around `890-918 ms`, round 110 had all six around `896-898 ms`, round 115 had all six around `655-656 ms`, and round 120 had all six around `551-552 ms`.

The debug trace identifies the route-context slow path. A slow `GET /api/dm/combat?workspace` at `2026-07-01T01:49:31Z` returned HTTP 200 in about `884.889 ms`, with nested `_dm_console_snapshot` about `881.641 ms`, `_dm_console_snapshot_payload` about `881.193 ms`, `_dm_tactical_snapshot` about `880.205 ms`, and `_lan_snapshot` about `879.776 ms`. Another route-context workspace read returned in about `624.684 ms`, with `_lan_snapshot` about `620.947 ms`.

The trace also contains many fast workspace reads, including late examples around `2-6 ms`, so the implementation should not assume the builder is always slow. The trace contains 56 standalone `_lan_snapshot` slow-span records plus one `_lan_snapshot` hang candidate around `24474.390 ms`; route offload will not solve every standalone LAN snapshot cost.

## Decision Questions

Do the harness p95/max spikes justify route-side read offload now?

Yes, narrowly. The shared p95/max spikes across health, readiness, and combat endpoints show a server responsiveness problem, not merely a slow DM route response. Because the route trace shows slow workspace reads dominated by synchronous DM-console tactical/LAN snapshot construction, route-side offload is justified as a transition mitigation to protect the event loop.

Is the evidence sufficient to identify which read path should be offloaded first?

Yes. The first path is the DM-console `GET /api/dm/combat` read when it requests tactical/workspace data. The combat-only route payload is often cheap, but the same route is the current route boundary and already passes explicit `include_tactical` context through `ServerRuntimeFacade.read_snapshot(dm_console)`.

Should the first implementation offload only `ServerRuntimeFacade.read_snapshot(dm_console)`, only the `GET /api/dm/combat` route, or a narrower tactical workspace builder path?

The first implementation should offload only the `GET /api/dm/combat` route's call to `ServerRuntimeFacade.read_snapshot(dm_console)`. It should not make `ServerRuntimeFacade.read_snapshot()` globally asynchronous, should not offload all snapshot modes, and should not introduce a lower-level threadpool inside `_dm_tactical_snapshot()` or `_lan_snapshot()`.

This keeps route auth, request parsing, and HTTP error mapping in the route layer while moving the existing synchronous snapshot build off the event loop. It also avoids making legacy tracker/Tk snapshot helpers callable from more contexts than they already are.

## Correctness Risks

- Legacy tracker state is not proven thread-safe. `_lan_snapshot()` reads and mutates tracker/LAN fields while building the snapshot, including canonical map state application, LAN positions, AoEs, obstacle/terrain state, and cache-related state.
- Tk/map-window state is not thread-safe. `_lan_snapshot()` may inspect `_map_window`, `winfo_exists()`, unit tokens, AoEs, obstacles, and rough terrain when a desktop map window exists. The first implementation must avoid claiming desktop/Tk safety beyond validated headless/server smoke.
- The one-shot `_cached_dm_snapshot` state can race if multiple worker reads or a broadcast prebuild touch it concurrently. The first implementation should avoid unbounded concurrent DM-console snapshot builds and must preserve the existing one-shot cache semantics.
- Request context must not be read inside the worker. The route must resolve `include_tactical` before offload and pass explicit `RuntimeSnapshotRequest.params`, preserving the current `read_snapshot(dm_console)` contract.
- Authentication must remain before offload. Admin checks and request-token handling must stay on the route side and no request object should be passed into the worker.
- Fail-closed behavior must be preserved. `runtime_not_ready` remains HTTP 503, other snapshot failures remain HTTP 500, unexpected exceptions remain generic HTTP 500, and no stale or partial payload fallback should be introduced.
- Trace/context propagation may change across a threadpool boundary. Any implementation must verify debug traces still show enough route and snapshot evidence to diagnose slow reads.
- Offload can hide event-loop blocking without reducing actual snapshot cost. If the worker pool saturates or standalone `_lan_snapshot` work still blocks the event loop, the harness may continue to show shared spikes.

## Required Validation For Implementation

Required focused validation for `WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation`:

```bash
git status --short
timeout 10s git diff --check
timeout 10s .venv/bin/python -m py_compile dnd_initative_tracker.py server_runtime.py tests/test_server_runtime.py
timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q
```

Add or update focused tests only if the implementation touches testable seams. Required assertions:

- `GET /api/dm/combat` still builds `RuntimeSnapshotRequest(snapshot_type="dm_console")`.
- `include_tactical` is resolved before offload and passed explicitly.
- `runtime_not_ready` still maps to HTTP 503.
- Other unsuccessful snapshot results still map to HTTP 500.
- Unexpected worker exceptions still map to the existing generic HTTP 500 route behavior.
- The route does not pass the FastAPI `Request` object into the worker.

Required developer smoke/evidence after implementation:

- Run headless/server smoke with debugging enabled.
- Open the DM console and DM control/workspace surface.
- Claim a LAN player session.
- Exercise `GET /api/dm/combat` and `GET /api/dm/combat?workspace=dmcontrol`.
- Run `scripts/server_responsiveness_harness.py` for the same 60 second, 0.5 second interval profile while heavier DM read-model activity is occurring.
- Record the harness JSONL and debug trace.
- Acceptance evidence should show health/readiness no longer spiking in lockstep with slow DM-console workspace reads. If `/health`, `/api/health`, `/ready`, and `/api/ready` still share the DM route's high p95/max spikes, the offload did not solve the responsiveness issue.
- Browser smoke must confirm no stale tactical/non-tactical data, no failed DM control load, no LAN claim regression, and no developer-visible responsiveness regression.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- App implementation in this decision pass.
- Test edits in this decision pass.
- Global facade-owned snapshot offload.
- A new asynchronous `ServerRuntimeFacade.read_snapshot()` public contract.
- Offload for all snapshot modes.
- Lower-level `_dm_tactical_snapshot()` or `_lan_snapshot()` threadpool execution.
- Tk/main-thread marshalling design.
- Cache TTL increase.
- Facade-owned snapshot cache.
- Durable polling/read-model cache.
- `_lan._cached_snapshot` route-side reuse.
- Static hydration contract changes.
- Snapshot schema or route payload changes.
- Queue behavior changes.
- LAN controller behavior changes.
- WebSocket behavior changes.
- Gameplay/combat behavior changes.
- More route adoption or direct gameplay route migration.
- Player-command routes.
- Combat mutation routes.
- Rules-aware move, AoE create, structures, ships, or boarding links.
- App-host/package topology changes.
- Launcher changes.
- Browser asset edits.
- Deploys, production commands, commits, or pushes.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle.

Allowed next action is to open:

`WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation`

The implementation must remain limited to route-side offload of the `GET /api/dm/combat` call to `ServerRuntimeFacade.read_snapshot(dm_console)` unless a new decision explicitly widens scope.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results are recorded in the final agent report.

# DM Console Combat Route/Request Overlap Planning Checkpoint - 2026-07-08

## Scope

This planning document outlines the route-visible `/api/dm/combat` latency analysis following composition refinement commit `82b996a` and smoke evidence commit `218f62e`. It analyzes why route-visible HTTP latency regressed (`936.898 ms` -> `1352.821 ms`) while underlying service and read-model execution durations improved materially.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Key Findings

1. **Service Latency Improvement**: `combat_service.combat_snapshot` p95 latency improved by ~23% from `500.641 ms` to `384.238 ms`. Similarly, `dm.console.combat_snapshot.service_call` improved from `501.904 ms` to `386.362 ms`.
2. **HTTP Latency Regression**: Despite the service improvement, `http.request:/api/dm/combat` p95 regressed from `936.898 ms` to `1352.821 ms`.
3. **Trace Metrics Gap**:
   - `dm.console.combat_snapshot.service_call` p95: `386.362 ms`
   - `dm.console.route_read_snapshot` p95: `1344.056 ms`
   - `http.request:/api/dm/combat` p95: `1352.821 ms`
   - **Attribution Gap**: There is an unexplained overhead of ~958 ms between the internal service-call completion and the route's returned snapshot completion.

## Answers to Key Questions

1. **Is the route-visible `/api/dm/combat` p95 regression strong evidence of a new bottleneck, or likely an outlier/sample-size artifact from a long idle run?**
   The regression is likely a sample-size and outlier artifact from a long idle run rather than a new systemic bottleneck. The HTTP request count was only 19 over a run of more than two hours, making the 95th percentile identical to the maximum value (`1352.821 ms`). This indicates that a single slow outlier request determined the p95 metric, whereas the previous benchmark had 25 requests over a short 10-minute run.

2. **Does the evidence isolate route/request overlap, response serialization, threadpool coordination, request concurrency, ASGI/Uvicorn overhead, or GC strongly enough for implementation?**
   No, the current evidence does not isolate these factors. We know a ~958 ms gap exists, but we cannot distinguish between JSON serialization of a large payload on the main thread, threadpool dispatch/return queue delays, concurrent events (WebSockets, ticks) blocking the event loop, ASGI/Uvicorn overhead, or garbage collection. Additional instrumentation is required to isolate these.

3. **Should the next item be controlled repeat smoke evidence, route/request-overlap instrumentation, implementation-decision planning, or pause?**
   The next item should be **targeted route/request-overlap instrumentation**. This will add low-cardinality timing spans to measure response serialization and threadpool scheduling latency, resolving the attribution gap.

4. **What additional evidence would distinguish route serialization from request overlap/threadpool scheduling?**
   Low-cardinality debug-trace spans measuring:
   - Synchronous JSON serialization of the payload in the route handler.
   - The threadpool dispatch queue delay (the delay between calling `run_in_threadpool` and the start of the snapshot reader inside the thread).
   - Event-loop blocking intervals or concurrent tasks (e.g., active WebSocket broadcasts, tick update cycles) overlapping with the HTTP request.

5. **Are `combat_service.combat_snapshot`, resource-pools, LAN units, route payload proxy, cache check, tactical merge, pending prompts, and size proxy still ruled out as immediate next implementation targets?**
   Yes. The composition refinement successfully reduced `combat_service.combat_snapshot` p95 to `384.238 ms`. Resource-pools is closed and fast (p95 `75.812 ms`). LAN units (p95 `20.869 ms`), payload proxy (`0.236 ms`), cache check (`1.172 ms`), tactical merge (`0.889 ms`), pending prompts (`0.727 ms`), and size proxy (`1.137 ms`) are all extremely fast and ruled out as bottlenecks.

6. **What exact files and spans should a future evidence/instrumentation slice inspect or instrument?**
   - **Files**: `dnd_initative_tracker.py` (specifically the GET `/api/dm/combat` route handler and `_dm_combat_read_snapshot_in_threadpool`) and `server_runtime.py`.
   - **Spans**:
     - `dm.console.route_serialization`: Timing the conversion of the data dictionary to the FastAPI/Starlette response.
     - `dm.console.threadpool_dispatch_queue`: Timing the dispatch latency before `read_snapshot` begins execution inside the threadpool.

7. **What must remain forbidden in any future slice?**
   - Do not edit app code.
   - Do not edit tests.
   - Do not edit production configuration or topology.
   - Do not alter response payload schemas or contents.
   - Do not change cache ownership or TTLs.
   - Do not modify WebSocket or queue routing.
   - Do not perform any deploy, restart, SSH, or push operations.

8. **Should startup `static_fields` and the small smoke bug remain deferred separately?**
   Yes. Startup `static_fields` is a one-time initialization cost (max `24069.121 ms` during startup) and does not impact steady-state latency. The small smoke bug remains deferred for separate bug-capture.

9. **What exact next work item should be recommended?**
   Recommend `WORK-20260708-dm-console-combat-route-request-overlap-instrumentation` as targeted instrumentation / evidence.

## Recommended Next Work Item

`WORK-20260708-dm-console-combat-route-request-overlap-instrumentation`
- **Type**: Targeted instrumentation / evidence.
- **Goal**: Add timing spans around FastAPI route response serialization and threadpool queue dispatch to attribute the route-visible latency gap.

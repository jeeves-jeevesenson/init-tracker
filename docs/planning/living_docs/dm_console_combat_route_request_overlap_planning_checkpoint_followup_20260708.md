# DM Console Combat Route/Request Overlap Planning Checkpoint Followup - 2026-07-08

## Scope

This planning document outlines the route-visible `/api/dm/combat` latency analysis following instrumentation commit `a01c398` and smoke evidence commit `7155e7b`. It details the investigation into why the route-visible HTTP latency max reached `1531.532 ms` while underlying service execution maxed at `677.440 ms`, and plans the next safe step.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Key Findings

1. **New Instrumentation Verification**:
   - `dm.console.threadpool_dispatch_queue` (count=6, p50=0.350ms, p95/max=88.188ms) proves scheduling delay is captured.
   - `dm.console.route_response_build` (count=6, p50=0.389ms, p95/max=0.429ms) proves payload serialization overhead is captured and is tiny.

2. **Attribution of the 1.5s HTTP Max**:
   - In the slowest request (`trace-ceb6dd1babf044c69131efce46601d53`), the HTTP request took `1531.532 ms`.
   - The threadpool dispatch queue took `88.188 ms`.
   - The internal read `_dm_console_snapshot` took `688.479 ms`.
   - The route response build took `0.392 ms`.
   - There remains a `715 ms` gap between the completion of `_dm_console_snapshot` inside the threadpool (`21:30:55.168Z`) and the return of `route_read_snapshot` on the main thread (`21:30:55.883Z`).
   - This gap is caused by **event-loop starvation / contention** due to concurrent execution of a heavy POST `/api/dm/combat/start` request (`trace-f49bdc73beeb4040897bb82685991348`) which ran synchronous `_lan_force_state_broadcast` work (taking `1299.706 ms` in total) on the main event loop, delaying the resumption of the GET combat snapshot coroutine.

3. **Sample Size Sensitivity**:
   - The GET `/api/dm/combat` route count is only 6. Direct optimization or routing changes based on this small, outlier-dominated sample size are not authorized.

---

## Answers to Key Questions

### 1. Does current evidence justify another implementation?
**No**. The current evidence shows the bottleneck is not in the route handler logic or response serialization (which is extremely fast). Instead, the latency spikes are due to event-loop contention/starvation caused by heavy concurrent write operations (POST requests and state broadcasts) blocking the event loop. Implementing direct route-visible changes would not address the event loop starvation.

### 2. Is the next safe item controlled repeat evidence with more `/api/dm/combat` samples, more instrumentation, implementation-decision planning, or pause?
The next safe item is **controlled repeat evidence**. We need to gather a larger, more representative sample size under controlled conditions to verify the frequency and impact of event-loop starvation during active combat modifications.

### 3. What exact evidence is missing to isolate the 1.5s route-visible max?
We need to correlate GET requests directly with concurrent write requests (like next-turn, hp adjustments, and moves) and their associated websocket broadcast cycles, tracing event-loop blocking intervals more systematically to confirm how frequently write operations starve concurrent read operations.

### 4. Is remaining route-visible latency better treated as service/read-model span variance, request scheduling overlap, event-loop contention, or sample-size artifact?
It is best treated as a combination of **event-loop contention / request scheduling overlap** (concurrency dynamics) and a **sample-size artifact** (since having only 6 HTTP requests makes the p95 metric extremely sensitive to a single concurrent outlier).

### 5. Should `route_response_build` remain ruled out?
**Yes**. With a p50 of `0.389 ms` and a max of `0.429 ms`, response payload construction and serialization are ruled out as a bottleneck.

### 6. Should `threadpool_dispatch_queue` remain a watch item but not an implementation target?
**Yes**. While it registered one modest `88.188 ms` outlier, its p50 is `0.350 ms`. It is not the driver of the 1.5s latency gap but should remain a watch item.

### 7. What exact future smoke instructions should be used if controlled repeat evidence is recommended?
Run a dense smoke-test sequence:
- Generate 30+ GET `/api/dm/combat` requests concurrently.
- Trigger active combat updates (e.g., POST `/api/dm/combat/next-turn`, moves, hp changes) during the GET request stream.
- Limit the run window to 5 minutes to maintain dense load shape and avoid long idle periods.

### 8. What exact future instrumentation seam should be used if more instrumentation is recommended?
If further instrumentation is desired, trace spans should be added to measure event-loop block times or task execution delays (e.g., a simple event-loop lag monitor or wrapping the websocket broadcast loop in detailed sub-spans).

### 9. What exact next work item should be recommended?
Recommend `WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence` as a controlled repeat evidence pass.

---

## Recommended Next Work Item

`WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence`
- **Type**: Controlled repeat evidence.
- **Goal**: Gather 30+ GET `/api/dm/combat` samples under dense load with active combat updates (next-turn, moves) over a short 5-minute window to confirm event-loop starvation dynamics and evaluate concurrency patterns.
- **Rules**: Keep resource-pools closed; keep startup static fields and the small smoke bug deferred. No app-code changes.

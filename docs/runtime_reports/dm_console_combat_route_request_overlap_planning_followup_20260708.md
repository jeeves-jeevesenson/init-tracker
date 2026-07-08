# DM Console Combat Route/Request Overlap Planning Followup Report - 2026-07-08

## Scope

This runtime report records the planning findings and details for the route-visible `/api/dm/combat` latency gap following instrumentation commit `a01c398` and smoke evidence commit `7155e7b`.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Key Metrics from Harness

- **Valid JSON objects**: `28,217`
- **Malformed/non-object lines**: `0`
- **Load shape**: `112` combatants, `10` players, `102` monsters.

| Span Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `29` | `274.290 ms` | `540.135 ms` | `677.440 ms` |
| `dm.console.combat_snapshot.service_call` | `23` | `272.907 ms` | `540.607 ms` | `678.747 ms` |
| `_dm_console_snapshot` | `20` | `247.468 ms` | `545.499 ms` | `688.479 ms` |
| `dm.console.threadpool_dispatch_queue` | `6` | `0.350 ms` | `88.188 ms` | `88.188 ms` |
| `dm.console.route_response_build` | `6` | `0.389 ms` | `0.429 ms` | `0.429 ms` |
| `dm.console.route_read_snapshot` | `6` | `299.477 ms` | `1492.095 ms` | `1492.095 ms` |
| `http.request:/api/dm/combat` | `6` | `331.813 ms` | `1531.532 ms` | `1531.532 ms` |

---

## Detailed Attribution of Latency Gap

In the slowest request (`trace-ceb6dd1babf044c69131efce46601d53`):
- `http.request` duration: `1531.532 ms`
- `dm.console.route_read_snapshot` duration: `1492.095 ms`
- `dm.console.threadpool_dispatch_queue` duration: `88.188 ms`
- `_dm_console_snapshot` duration: `688.479 ms`
- `dm.console.route_response_build` duration: `0.392 ms`

The remaining unexplained latency is `1531.532 - 88.188 - 688.479 - 0.392 = 754.473 ms` (or a `715 ms` gap between the end of `_dm_console_snapshot` and the end of `route_read_snapshot`).

This gap is isolated to **event-loop starvation / contention**:
1. At `21:30:54.389Z`, the GET `/api/dm/combat` request starts and offloads snapshot reading to a threadpool thread.
2. At `21:30:54.479Z`, `_dm_console_snapshot` begins execution inside the threadpool.
3. At `21:30:54.605Z`, a concurrent POST `/api/dm/combat/start` request begins execution. This handler runs synchronously on the main event loop, calling `InitiativeTracker._lan_force_state_broadcast` which triggers a heavy snapshot construction and websocket broadcast cycle.
4. At `21:30:55.168Z`, the GET request's threadpool worker completes and signals the event loop to resume the route handler coroutine.
5. Because the main event loop is blocked running the POST request and its associated broadcast tasks (which run until `21:30:55.896Z`), the resumed coroutine is starved and cannot be scheduled until `21:30:55.883Z` (a delay of `715 ms`).
6. Once scheduled, the GET handler builds the response and finishes in less than `1 ms`.

---

## Decision

1. **Keep commits `7155e7b` and `a01c398`**: The new instrumentation spans are accepted and provide highly actionable insights.
2. **Do not authorize implementation**: Direct optimization of the route handler is not appropriate because the bottleneck is event-loop block times, not route handler processing or serialization.
3. **Controlled Repeat Evidence**: Recommend gathering more data under a controlled environment with 30+ requests to confirm the concurrency dynamics.
4. **Deferred**: Startup static fields and the small smoke bug remain separately deferred. Resource-pools remains closed.

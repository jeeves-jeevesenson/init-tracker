# DM Console Combat Route/Request Overlap Instrumentation Smoke Evidence - 2026-07-08

## Scope

This runtime report records a bounded docs/evidence checkpoint using post-instrumentation smoke/debug-trace evidence after instrumentation commit `a01c398`.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Evidence Files

- Smoke log: [WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture_smoke-server_20260708-162049.log](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture_smoke-server_20260708-162049.log)
- Debug trace: [debug-trace-20260708-162049.jsonl](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/logs/debug-trace-20260708-162049.jsonl)

## Smoke Facts

The smoke log records:
- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm` (`http://10.3.25.235:8787/dm`).
- Player LAN surface advertised on `/` (`http://10.3.25.235:8787/`).
- LAN server hoisted on port `8787`.
- Two browser LAN WebSocket sessions connected.
- One browser LAN WebSocket session disconnected.
- LAN session claimed Dorian (Assigned).

The trace tail records `http.request.end` for `/api/dm/combat` with `status_code=200`.

This proves the captured startup/LAN/session/claim and DM combat read path still work with the new instrumentation.

## Harness Summary

Harness command:
```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-162049.jsonl
```

Input parse result:
- valid JSON objects: `28,217`
- malformed/non-object lines: `0`

Load shape in steady rows:
- combatants: `112`
- players: `10`
- monsters: `102`

Key latency rows:

| Target | Count | min | p50 | p95 | Max | >=100ms | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `733` | `1.753 ms` | `16.594 ms` | `80.678 ms` | `24622.011 ms` | `18` | `4` | `1` |
| `lan.snapshot.resource_pools` | `733` | `0.071 ms` | `14.342 ms` | `77.850 ms` | `743.560 ms` | `3` | `2` | `0` |
| `lan.snapshot.units` | `733` | `0.067 ms` | `0.078 ms` | `22.248 ms` | `42.664 ms` | `0` | `0` | `0` |
| `_dm_console_snapshot` | `20` | `0.364 ms` | `247.468 ms` | `545.499 ms` | `688.479 ms` | `12` | `10` | `0` |
| `_dm_console_snapshot_payload` | `25` | `0.843 ms` | `296.983 ms` | `542.872 ms` | `685.221 ms` | `18` | `16` | `0` |
| `combat_service.combat_snapshot` | `29` | `0.221 ms` | `274.290 ms` | `540.135 ms` | `677.440 ms` | `24` | `19` | `0` |
| `dm.console.combat_snapshot` | `23` | `0.707 ms` | `273.308 ms` | `541.861 ms` | `680.338 ms` | `18` | `15` | `0` |
| `dm.console.combat_snapshot.service_call` | `23` | `0.390 ms` | `272.907 ms` | `540.607 ms` | `678.747 ms` | `18` | `15` | `0` |
| `dm.console.route_read_snapshot` | `6` | `2.796 ms` | `299.477 ms` | `1492.095 ms` | `1492.095 ms` | `4` | `4` | `1` |
| `dm.console.route_payload_proxy` | `6` | `0.174 ms` | `0.186 ms` | `0.209 ms` | `0.209 ms` | `0` | `0` | `0` |
| `dm.console.snapshot.cache_check` | `18` | `0.082 ms` | `0.092 ms` | `0.936 ms` | `0.936 ms` | `0` | `0` | `0` |
| `dm.console.snapshot.payload` | `18` | `1.036 ms` | `253.775 ms` | `686.531 ms` | `686.531 ms` | `12` | `10` | `0` |
| `dm.console.payload.tactical_merge` | `25` | `0.064 ms` | `0.072 ms` | `0.533 ms` | `0.724 ms` | `0` | `0` | `0` |
| `dm.console.payload.pending_prompts` | `25` | `0.081 ms` | `0.091 ms` | `0.720 ms` | `0.880 ms` | `0` | `0` | `0` |
| `dm.console.payload.size_proxy` | `25` | `0.139 ms` | `0.157 ms` | `1.050 ms` | `20.595 ms` | `0` | `0` | `0` |
| `dm.console.threadpool_dispatch_queue` | `6` | `0.231 ms` | `0.350 ms` | `88.188 ms` | `88.188 ms` | `0` | `0` | `0` |
| `dm.console.route_response_build` | `6` | `0.375 ms` | `0.389 ms` | `0.429 ms` | `0.429 ms` | `0` | `0` | `0` |
| `http.request:/api/dm/combat` | `6` | `4.074 ms` | `331.813 ms` | `1531.532 ms` | `1531.532 ms` | `4` | `4` | `1` |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24173.505 ms`.

## Interpretation & Decision

Keep post-instrumentation commit `a01c398`.

1. **Instrumentation Verification**: The post-instrumentation smoke proves the new spans are successfully emitted, captured, and correctly aggregated by the latency harness.
2. **Response Build Overhead Ruled Out**: `dm.console.route_response_build` metrics (`p50=0.389ms`, `p95=0.429ms`, `max=0.429ms`) rule out route response serialization and payload construction/copy as a bottleneck.
3. **Threadpool Queue Scheduling Delay**: `dm.console.threadpool_dispatch_queue` shows `p50=0.350ms` and `p95/max=88.188ms`. This indicates a single modest outlier scheduling delay in the threadpool, but it does not account for the major difference between the route's maximum duration (`1531.532ms`) and internal read execution (`688.479ms` max for `_dm_console_snapshot`).
4. **Sample Size Sensitivity**: The route-visible `/api/dm/combat` p95 (`1531.532ms`) and `dm.console.route_read_snapshot` p95 (`1492.095ms`) are highly sample-size-sensitive due to having only 6 HTTP requests. Direct optimization implementation based solely on this evidence is not authorized.
5. **Attribution of remaining latency**: The ~800ms gap in the maximum case (`1531.532ms` HTTP request vs `688.479ms` console snapshot) is not explained by the threadpool dispatch queue delay (`88.188ms`) or response construction (`0.429ms`) alone. This points to potential ASGI event loop starvation or request-overlap bottlenecks.

Resource-pools remains closed. Startup-only static fields and the small smoke bug remain separately deferred.

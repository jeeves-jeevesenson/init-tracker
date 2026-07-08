# DM Console Combat Route/Request Overlap Instrumentation Smoke Evidence Capture - 2026-07-08

## Scope

This document records a bounded docs/evidence checkpoint for the DM console combat route/request overlap instrumentation smoke/debug trace captured after implementation commit `a01c398`.

No app implementation, optimization, tests, log edits, server start, browser smoke, deploy, restart, SSH, push, commit, route change, payload/schema change, snapshot schema change, resource-pools/cache/TTL/static-fields change, WebSocket/queue/auth/claims/reconnect change, persistence change, visibility/hidden-information change, map/terrain/monster-control change, encounter state change, production topology change, gameplay change, startup static-fields work, or small smoke bug patch occurred.

## Evidence Inputs

- Smoke log: [WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture_smoke-server_20260708-162049.log](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-instrumentation-smoke-evidence-capture_smoke-server_20260708-162049.log)
- Debug trace: [debug-trace-20260708-162049.jsonl](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/logs/debug-trace-20260708-162049.jsonl)
- Implementation basis: `a01c398`

The smoke log records headless tracker startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one LAN disconnect, and Dorian claim.

The trace tail records `http.request.end` for `/api/dm/combat` with `status_code=200`.

## Harness Evidence

The harness parsed `28,217` valid JSON objects and `0` malformed/non-object lines.

Steady rows show about `112` combatants, `10` players, and `102` monsters.

Primary read-model and new instrumentation rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `29` | `274.290 ms` | `540.135 ms` | `677.440 ms` |
| `dm.console.combat_snapshot.service_call` | `23` | `272.907 ms` | `540.607 ms` | `678.747 ms` |
| `dm.console.route_read_snapshot` | `6` | `299.477 ms` | `1492.095 ms` | `1492.095 ms` |
| `http.request:/api/dm/combat` | `6` | `331.813 ms` | `1531.532 ms` | `1531.532 ms` |
| `dm.console.threadpool_dispatch_queue` | `6` | `0.350 ms` | `88.188 ms` | `88.188 ms` |
| `dm.console.route_response_build` | `6` | `0.389 ms` | `0.429 ms` | `0.429 ms` |

Small wrapper/proxy rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `dm.console.route_payload_proxy` | `6` | `0.186 ms` | `0.209 ms` | `0.209 ms` |
| `dm.console.snapshot.cache_check` | `18` | `0.092 ms` | `0.936 ms` | `0.936 ms` |
| `dm.console.payload.tactical_merge` | `25` | `0.072 ms` | `0.533 ms` | `0.724 ms` |
| `dm.console.payload.pending_prompts` | `25` | `0.091 ms` | `0.720 ms` | `0.880 ms` |
| `dm.console.payload.size_proxy` | `25` | `0.157 ms` | `1.050 ms` | `20.595 ms` |

LAN/resource rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `733` | `16.594 ms` | `80.678 ms` | `24622.011 ms` | `4` | `1` |
| `lan.snapshot.resource_pools` | `733` | `14.342 ms` | `77.850 ms` | `743.560 ms` | `2` | `0` |
| `lan.snapshot.units` | `733` | `0.078 ms` | `22.248 ms` | `42.664 ms` | `0` | `0` |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24173.505 ms`.

## Evidence Decision

Keep instrumentation commit `a01c398`. The new instrumentation spans are successfully emitted, captured, and aggregated.

The new spans reveal:
1. **`dm.console.route_response_build`** p95 of `0.429 ms` rules out response payload construction and serialization as a bottleneck.
2. **`dm.console.threadpool_dispatch_queue`** p95 of `88.188 ms` shows only a single modest outlier queue delay, which does not explain the full `1531.532 ms` HTTP max request latency.
3. The remaining HTTP request slow path (`1531.532 ms` max request duration vs `688.479 ms` max internal read duration) remains dominated by a distinct gap (~800 ms in the maximum case). Since the queue scheduling delay and response serialization combined are less than `90 ms`, the remaining gap is likely attributed to ASGI event loop starvation or request-overlap bottlenecks.

## Next Decision

Do not authorize direct implementation from this smoke alone. The p95 is highly sample-size-sensitive due to having only 6 HTTP requests.

Recommend a narrow planning and evidence checkpoint focused on the request-overlap, event-loop blocking, and ASGI threadpool coordination dynamics.

Recommended next work item:

`WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint-followup`

Type: planning / evidence checkpoint.

Goal: Map event-loop latency, coordinate ASGI-Uvicorn worker settings, check request-overlap serialization behavior, and identify safe non-blocking boundaries.

## Deferred

- Startup-only `lan.snapshot.static_fields` remains deferred separately.
- Resource-pools remains closed.
- The small smoke bug remains deferred separately and was not patched.
- App code, tests, scripts, logs, routes, payloads, cache/resource-pools/static-fields behavior, WebSockets, queues, auth/claims/reconnect, production topology, visibility rules, and gameplay behavior remain unchanged.

# DM Console Combat Service Read-Model Composition Smoke Evidence Capture - 2026-07-08

## Scope

This document records a bounded docs/evidence checkpoint for the DM console combat service/read-model composition smoke/debug trace captured after implementation commit `82b996a`.

No app implementation, optimization, tests, log edits, server start, browser smoke, deploy, restart, SSH, push, commit, route change, payload/schema change, snapshot schema change, resource-pools/cache/TTL/static-fields change, WebSocket/queue/auth/claims/reconnect change, persistence change, visibility/hidden-information change, map/terrain/monster-control change, encounter state change, production topology change, gameplay change, startup static-fields work, or small smoke bug patch occurred.

## Evidence Inputs

- Smoke log: `logs/smoke/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture_smoke-server_20260708-122320.log`
- Debug trace: `logs/debug-trace-20260708-122320.jsonl`
- Implementation basis: `82b996a`

The smoke log records headless tracker startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one LAN disconnect, Malagrou claim, Malagrou unclaim, and Old Man claim.

The trace tail records `http.request.end` for `/api/dm/combat` with `status_code=200`.

## Harness Evidence

The harness parsed `219,108` valid JSON objects and `0` malformed/non-object lines.

Steady rows show about `110-112` combatants, `10` players, and `100-102` monsters.

Primary read-model rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `61` | `264.293 ms` | `384.238 ms` | `557.982 ms` |
| `dm.console.combat_snapshot` | `52` | `268.450 ms` | `388.826 ms` | `561.589 ms` |
| `dm.console.combat_snapshot.service_call` | `52` | `264.635 ms` | `386.362 ms` | `559.305 ms` |
| `_dm_console_snapshot_payload` | `53` | `291.226 ms` | `424.810 ms` | `605.028 ms` |
| `_dm_console_snapshot` | `42` | `291.005 ms` | `401.803 ms` | `607.699 ms` |
| `dm.console.route_read_snapshot` | `19` | `352.289 ms` | `1344.056 ms` | `1344.056 ms` |
| `http.request:/api/dm/combat` | `19` | `383.034 ms` | `1352.821 ms` | `1352.821 ms` |

Small wrapper/proxy rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `dm.console.route_payload_proxy` | `19` | `0.194 ms` | `0.236 ms` | `0.236 ms` |
| `dm.console.snapshot.cache_check` | `42` | `0.093 ms` | `1.172 ms` | `16.161 ms` |
| `dm.console.combat_snapshot.copy` | `52` | `0.073 ms` | `0.616 ms` | `20.548 ms` |
| `dm.console.payload.tactical_merge` | `53` | `0.068 ms` | `0.889 ms` | `20.858 ms` |
| `dm.console.payload.pending_prompts` | `53` | `0.093 ms` | `0.727 ms` | `0.832 ms` |
| `dm.console.payload.size_proxy` | `53` | `0.152 ms` | `1.137 ms` | `1.295 ms` |

LAN/resource rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `8589` | `15.982 ms` | `77.896 ms` | `24515.255 ms` | `9` | `1` |
| `lan.snapshot.resource_pools` | `8589` | `13.917 ms` | `75.812 ms` | `767.139 ms` | `9` | `0` |
| `lan.snapshot.units` | `8589` | `0.073 ms` | `20.869 ms` | `61.032 ms` | `0` | `0` |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24069.121 ms`.

## Comparison Against 2026-07-07 targeted-smoke evidence

- `combat_service.combat_snapshot` p95: `500.641 ms` -> `384.238 ms` (~23% reduction).
- `dm.console.combat_snapshot.service_call` p95: `501.904 ms` -> `386.362 ms` (~23% reduction).
- `http.request:/api/dm/combat` p95: `936.898 ms` -> `1352.821 ms` (regressed/increased).

The direct combat service and read-model composition spans show material improvement. The route-visible HTTP request p95 regression is driven by a single slow request outlier over the much longer run (more than 2 hours vs. less than 15 minutes, with only 19 HTTP requests, making the 95th percentile identical to the maximum value).

## Evidence Decision

Keep composition refinement commit `82b996a`. The core read-model composition latency has improved materially as measured by the service spans.

The following wrapper and LAN components remain ruled out as primary bottlenecks:
- `dm.console.route_payload_proxy`
- `dm.console.combat_snapshot.copy`
- `dm.console.snapshot.cache_check`
- `dm.console.payload.tactical_merge`
- `dm.console.payload.pending_prompts`
- `dm.console.payload.size_proxy`
- `lan.snapshot.resource_pools`
- `lan.snapshot.units`

Remaining latency in the HTTP route (`http.request:/api/dm/combat` p50 `383.034 ms` / p95 `1352.821 ms`) is no longer dominated solely by `combat_service.combat_snapshot`. There is a distinct gap between the service-call duration and the route read/request completion, suggesting route/request serialization, thread coordination, or scheduling overlap as a separate optimization boundary.

## Next Decision

Do not authorize another immediate implementation from this smoke alone. Recommend a narrow route/request-overlap planning/evidence checkpoint.

Recommended next work item:

`WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint`

Type: planning / evidence checkpoint.

Goal: Investigate route/request serialization, event-loop blocking, ASGI-Uvicorn coordination, and request-concurrency overlap overhead to identify safe seams for route-visible latency reduction.

## Deferred

- Startup-only `lan.snapshot.static_fields` remains deferred separately.
- Resource-pools remains closed.
- The small smoke bug remains deferred separately and was not patched.
- App code, tests, scripts, logs, routes, payloads, cache/resource-pools/static-fields behavior, WebSockets, queues, auth/claims/reconnect, production topology, visibility rules, and gameplay behavior remain unchanged.

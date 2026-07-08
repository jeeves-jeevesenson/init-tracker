# DM Console Combat Service Read-Model Composition Smoke Evidence - 2026-07-08

## Scope

This runtime report records a bounded docs/evidence checkpoint using post-implementation smoke/debug-trace evidence after composition refinement commit `82b996a`.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture_smoke-server_20260708-122320.log`
- Debug trace: `logs/debug-trace-20260708-122320.jsonl`

## Smoke Facts

The smoke log records:
- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN sessions connected.
- One LAN session disconnected.
- LAN session claimed Malagrou.
- LAN session unclaimed Malagrou.
- LAN session claimed Old Man.

The trace tail records `http.request.end` for `/api/dm/combat` with `status_code=200`.

This proves the captured startup/LAN/session/claim and DM combat read path still work with the composition refinement.

## Harness Summary

Harness command:
```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-122320.jsonl
```

Input parse result:
- valid JSON objects: `219,108`
- malformed/non-object lines: `0`

Load shape in steady rows:
- combatants: `110-112`
- players: `10`
- monsters: `100-102`

Key latency rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `8589` | `15.982 ms` | `77.896 ms` | `24515.255 ms` | `9` | `1` |
| `lan.snapshot.resource_pools` | `8589` | `13.917 ms` | `75.812 ms` | `767.139 ms` | `9` | `0` |
| `lan.snapshot.units` | `8589` | `0.073 ms` | `20.869 ms` | `61.032 ms` | `0` | `0` |
| `_dm_console_snapshot` | `42` | `291.005 ms` | `401.803 ms` | `607.699 ms` | `25` | `0` |
| `_dm_console_snapshot_payload` | `53` | `291.226 ms` | `424.810 ms` | `605.028 ms` | `35` | `0` |
| `combat_service.combat_snapshot` | `61` | `264.293 ms` | `384.238 ms` | `557.982 ms` | `32` | `0` |
| `dm.console.combat_snapshot` | `52` | `268.450 ms` | `388.826 ms` | `561.589 ms` | `28` | `0` |
| `dm.console.combat_snapshot.service_call` | `52` | `264.635 ms` | `386.362 ms` | `559.305 ms` | `28` | `0` |
| `dm.console.combat_snapshot.copy` | `52` | `0.073 ms` | `0.616 ms` | `20.548 ms` | `0` | `0` |
| `dm.console.route_read_snapshot` | `19` | `352.289 ms` | `1344.056 ms` | `1344.056 ms` | `17` | `1` |
| `dm.console.route_payload_proxy` | `19` | `0.194 ms` | `0.236 ms` | `0.236 ms` | `0` | `0` |
| `dm.console.snapshot.cache_check` | `42` | `0.093 ms` | `1.172 ms` | `16.161 ms` | `0` | `0` |
| `dm.console.snapshot.payload` | `35` | `316.571 ms` | `425.060 ms` | `606.140 ms` | `25` | `0` |
| `dm.console.payload.tactical_merge` | `53` | `0.068 ms` | `0.889 ms` | `20.858 ms` | `0` | `0` |
| `dm.console.payload.pending_prompts` | `53` | `0.093 ms` | `0.727 ms` | `0.832 ms` | `0` | `0` |
| `dm.console.payload.size_proxy` | `53` | `0.152 ms` | `1.137 ms` | `1.295 ms` | `0` | `0` |
| `http.request:/api/dm/combat` | `19` | `383.034 ms` | `1352.821 ms` | `1352.821 ms` | `17` | `1` |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24069.121 ms`.

## Interpretation & Decision

Keep composition refinement commit `82b996a`.

The direct combat service read-model composition spans show material improvement compared to the 2026-07-07 targeted-smoke evidence:
- `combat_service.combat_snapshot` p95: `500.641 ms` -> `384.238 ms` (~23% reduction).
- `dm.console.combat_snapshot.service_call` p95: `501.904 ms` -> `386.362 ms` (~23% reduction).

The route-visible HTTP request p95 regression (`936.898 ms` -> `1352.821 ms`) is driven by a single slow request outlier over a much longer run (2+ hours with only 19 HTTP requests, making the 95th percentile identical to the maximum value).

The cheap substeps are ruled out as primary bottlenecks:
- route payload proxy
- combat snapshot copy
- cache check
- tactical merge
- pending prompts
- size proxy
- LAN units
- resource pools

Resource-pools remains closed. Startup-only static fields remains a separate deferred startup outlier.

The next safe latency item is:
`WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint`

Type: planning / evidence checkpoint.
Goal: Investigate route/request serialization, event-loop blocking, ASGI-Uvicorn coordination, and request-concurrency overlap overhead to identify safe seams for route-visible latency reduction.

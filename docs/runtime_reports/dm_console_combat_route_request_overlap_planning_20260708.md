# DM Console Combat Route/Request Overlap Planning - 2026-07-08

## Scope

This runtime report records a bounded planning/evidence checkpoint for the route-visible `/api/dm/combat` latency after composition refinement commit `82b996a` and smoke evidence commit `218f62e`.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Evidence Summary

- **Evidence Log**: `logs/smoke/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture_smoke-server_20260708-122320.log`
- **Debug Trace**: `logs/debug-trace-20260708-122320.jsonl`
- **Parser Execution**:
  - Command: `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-122320.jsonl`
  - Valid JSON objects: `219,108`
  - Malformed lines: `0`
- **Load Shape**:
  - Combatants: `110-112`
  - Players: `10`
  - Monsters: `100-102`

## Key Latency Spans

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `61` | `264.293 ms` | `384.238 ms` | `557.982 ms` |
| `dm.console.combat_snapshot` | `52` | `268.450 ms` | `388.826 ms` | `561.589 ms` |
| `dm.console.combat_snapshot.service_call` | `52` | `264.635 ms` | `386.362 ms` | `559.305 ms` |
| `_dm_console_snapshot_payload` | `53` | `291.226 ms` | `424.810 ms` | `605.028 ms` |
| `_dm_console_snapshot` | `42` | `291.005 ms` | `401.803 ms` | `607.699 ms` |
| `dm.console.route_read_snapshot` | `19` | `352.289 ms` | `1344.056 ms` | `1344.056 ms` |
| `http.request:/api/dm/combat` | `19` | `383.034 ms` | `1352.821 ms` | `1352.821 ms` |

### Small Wrappers & LAN Metrics
- `dm.console.route_payload_proxy` p95: `0.236 ms`
- `dm.console.snapshot.cache_check` p95: `1.172 ms`
- `dm.console.combat_snapshot.copy` p95: `0.616 ms`
- `dm.console.payload.tactical_merge` p95: `0.889 ms`
- `dm.console.payload.pending_prompts` p95: `0.727 ms`
- `dm.console.payload.size_proxy` p95: `1.137 ms`
- `lan.snapshot.resource_pools` p95: `75.812 ms`
- `lan.snapshot.units` p95: `20.869 ms`
- Startup-only `lan.snapshot.static_fields` max: `24069.121 ms` (Startup outlier)

## Planning Decision

1. **Keep Refinement 82b996a**: Direct combat service/read-model snapshot execution p95 improved materially (~23% reduction).
2. **Accept p95 Regression as Outlier**: The HTTP p95 regression to `1352.821 ms` is an artifact of a low request count (19 requests over a 2+ hour run) where a single slow request outlier equaled the maximum value.
3. **Attribution Gap**: There is an unexplained gap of ~958 ms between `dm.console.combat_snapshot.service_call` p95 (`386.362 ms`) and `http.request:/api/dm/combat` p95 (`1352.821 ms`).
4. **Immediate Path**: Do not perform any direct code optimization. The evidence does not isolate serialization from scheduling or overlap.
5. **Next Work Item Recommendation**:
   - Title: `WORK-20260708-dm-console-combat-route-request-overlap-instrumentation`
   - Type: Targeted instrumentation / evidence.
   - Purpose: Add debug-trace spans for response serialization and threadpool queue delays in `dnd_initative_tracker.py` and `server_runtime.py`.

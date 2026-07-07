# DM Console Combat Read-Model Targeted Smoke Evidence Capture - 2026-07-07

## Scope

This document records a bounded docs/evidence checkpoint for the DM console combat read-model targeted smoke/debug trace captured after instrumentation commit `e05fb8f`.

No app implementation, optimization, tests, log edits, server start, browser smoke, deploy, restart, SSH, push, commit, route change, payload/schema change, snapshot schema change, resource-pools/cache/TTL/static-fields change, WebSocket/queue/auth/claims/reconnect change, persistence change, visibility/hidden-information change, map/terrain/monster-control change, encounter state change, production topology change, gameplay change, startup static-fields work, or small smoke bug patch occurred.

## Evidence Inputs

- Smoke log: `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`
- Debug trace: `logs/debug-trace-20260707-105332.jsonl`
- Instrumentation basis: `e05fb8f`

The smoke log records headless tracker startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one LAN disconnect, and Dorian claim. The captured tail does not show unclaim before `Ctrl+C`.

The trace tail records `http.request.end` for `/api/dm/combat` with `status_code=200` and `response_bytes=303029`.

## Harness Evidence

The harness parsed `45,277` valid JSON objects and `0` malformed/non-object lines.

Steady rows show `112` combatants, `10` players, and `102` monsters.

Primary read-model rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `44` | `269.380 ms` | `500.641 ms` | `660.390 ms` |
| `dm.console.combat_snapshot` | `41` | `279.927 ms` | `504.178 ms` | `662.108 ms` |
| `dm.console.combat_snapshot.service_call` | `41` | `270.945 ms` | `501.904 ms` | `660.880 ms` |
| `_dm_console_snapshot_payload` | `41` | `326.950 ms` | `620.516 ms` | `663.121 ms` |
| `_dm_console_snapshot` | `39` | `329.854 ms` | `648.836 ms` | `665.728 ms` |
| `dm.console.route_read_snapshot` | `25` | `352.772 ms` | `851.266 ms` | `987.922 ms` |
| `http.request:/api/dm/combat` | `25` | `385.621 ms` | `936.898 ms` | `1039.199 ms` |

Small wrapper/proxy rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `dm.console.route_payload_proxy` | `25` | `0.186 ms` | `0.514 ms` | `25.874 ms` |
| `dm.console.snapshot.cache_check` | `39` | `0.099 ms` | `0.914 ms` | `15.383 ms` |
| `dm.console.combat_snapshot.copy` | `41` | `0.080 ms` | `0.719 ms` | `0.910 ms` |
| `dm.console.payload.tactical_merge` | `41` | `0.074 ms` | `4.043 ms` | `21.184 ms` |
| `dm.console.payload.pending_prompts` | `41` | `0.093 ms` | `0.927 ms` | `1.099 ms` |
| `dm.console.payload.size_proxy` | `41` | `0.157 ms` | `1.000 ms` | `1.467 ms` |

LAN/resource rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `1140` | `4.443 ms` | `52.504 ms` | `24923.044 ms` | `4` | `1` |
| `lan.snapshot.resource_pools` | `1140` | `0.084 ms` | `14.497 ms` | `806.993 ms` | `4` | `0` |
| `lan.snapshot.units` | `1140` | `1.811 ms` | `21.864 ms` | `51.668 ms` | `0` | `0` |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24475.459 ms`.

## Evidence Decision

Keep instrumentation commit `e05fb8f`.

Resource-pools remains closed. `lan.snapshot.resource_pools` p50/p95 are small in the new trace, and the recurring DM console combat route/read-model latency is no longer attributable to resource-pools.

The primary remaining actionable span is `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call`. The service-call rows nearly match the outer `dm.console.combat_snapshot` row and drive most of `_dm_console_snapshot_payload`, `_dm_console_snapshot`, route read, and HTTP route-visible timing.

The following are ruled out as primary bottlenecks in this trace:

- `dm.console.route_payload_proxy`
- `dm.console.combat_snapshot.copy`
- `dm.console.snapshot.cache_check`
- `dm.console.payload.tactical_merge`
- `dm.console.payload.pending_prompts`
- `dm.console.payload.size_proxy`
- `lan.snapshot.resource_pools`
- `lan.snapshot.units`

The `112`-combatant / `102`-monster shape points toward scale/read-model composition in the combat service path.

## Next Decision

Direct implementation is not selected from this task. The evidence isolates the expensive service/read-model call, but this checkpoint did not inspect or authorize service-internal code changes and does not yet document an already-clear behavior-preserving implementation seam.

Recommended next work item:

`WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint`

Recommended type:

Planning / implementation decision.

Recommended goal:

Inspect only the narrow combat service/read-model implementation needed to decide whether a behavior-preserving implementation seam exists for the `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` latency. Do not implement during that checkpoint unless a later active item explicitly authorizes implementation.

## Deferred

Startup-only `lan.snapshot.static_fields` remains deferred separately.

The small smoke bug remains separate bug-capture scope and was not patched.

Routes, route bodies, route registration, response payloads, snapshot schemas, resource-pools behavior, cache behavior, TTLs, static hydration, WebSockets, queues, auth/claims/reconnect, persistence, visibility, hidden-information rules, map/terrain behavior, monster control, encounter state semantics, production topology, deploy/restart/SSH behavior, and gameplay behavior remain unchanged.

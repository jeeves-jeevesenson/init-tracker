# DM Console Combat Read-Model Targeted Smoke Evidence - 2026-07-07

## Scope

This runtime report records a bounded docs/evidence checkpoint using already captured targeted smoke/debug-trace evidence after instrumentation commit `e05fb8f`.

No app code, tests, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`
- Debug trace: `logs/debug-trace-20260707-105332.jsonl`

## Smoke Facts

The smoke log records:

- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN sessions connected.
- One LAN session disconnected.
- One LAN session claimed Dorian.
- The captured smoke tail does not show unclaim before `Ctrl+C`.

The trace tail records:

- `http.request.end` for `/api/dm/combat`
- `status_code=200`
- `response_bytes=303029`

This proves the captured startup/LAN/session/claim and DM combat read path still work with the targeted instrumentation. It does not claim broader gameplay, unclaim coverage, full disconnect semantics, production readiness, or browser smoke coverage beyond the captured evidence.

## Harness Summary

Harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
```

Input parse result:

- valid JSON objects: `45,277`
- malformed/non-object lines: `0`

Load shape in steady rows:

- combatants: `112`
- players: `10`
- monsters: `102`

Key latency rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `1140` | `4.443 ms` | `52.504 ms` | `24923.044 ms` | `4` | `1` |
| `lan.snapshot.resource_pools` | `1140` | `0.084 ms` | `14.497 ms` | `806.993 ms` | `4` | `0` |
| `lan.snapshot.units` | `1140` | `1.811 ms` | `21.864 ms` | `51.668 ms` | `0` | `0` |
| `_dm_console_snapshot` | `39` | `329.854 ms` | `648.836 ms` | `665.728 ms` | `31` | `0` |
| `_dm_console_snapshot_payload` | `41` | `326.950 ms` | `620.516 ms` | `663.121 ms` | `35` | `0` |
| `combat_service.combat_snapshot` | `44` | `269.380 ms` | `500.641 ms` | `660.390 ms` | `27` | `0` |
| `dm.console.combat_snapshot` | `41` | `279.927 ms` | `504.178 ms` | `662.108 ms` | `29` | `0` |
| `dm.console.combat_snapshot.service_call` | `41` | `270.945 ms` | `501.904 ms` | `660.880 ms` | `27` | `0` |
| `dm.console.combat_snapshot.copy` | `41` | `0.080 ms` | `0.719 ms` | `0.910 ms` | `0` | `0` |
| `dm.console.route_read_snapshot` | `25` | `352.772 ms` | `851.266 ms` | `987.922 ms` | `23` | `0` |
| `dm.console.route_payload_proxy` | `25` | `0.186 ms` | `0.514 ms` | `25.874 ms` | `0` | `0` |
| `dm.console.snapshot.cache_check` | `39` | `0.099 ms` | `0.914 ms` | `15.383 ms` | `0` | `0` |
| `dm.console.snapshot.payload` | `36` | `328.183 ms` | `647.329 ms` | `664.048 ms` | `31` | `0` |
| `dm.console.payload.tactical_merge` | `41` | `0.074 ms` | `4.043 ms` | `21.184 ms` | `0` | `0` |
| `dm.console.payload.pending_prompts` | `41` | `0.093 ms` | `0.927 ms` | `1.099 ms` | `0` | `0` |
| `dm.console.payload.size_proxy` | `41` | `0.157 ms` | `1.000 ms` | `1.467 ms` | `0` | `0` |
| `http.request:/api/dm/combat` | `25` | `385.621 ms` | `936.898 ms` | `1039.199 ms` | `23` | `1` |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24475.459 ms`.

## Interpretation

The targeted instrumentation is accepted and should remain. The new trace narrows the remaining latency to the combat service/read-model call:

- `combat_service.combat_snapshot` p50/p95/max are `269.380 ms` / `500.641 ms` / `660.390 ms`.
- `dm.console.combat_snapshot.service_call` p50/p95/max are `270.945 ms` / `501.904 ms` / `660.880 ms`.
- `dm.console.combat_snapshot` p50/p95/max are `279.927 ms` / `504.178 ms` / `662.108 ms`.

The wrappers add visible route/read overhead but are not the primary seam:

- `_dm_console_snapshot_payload` and `_dm_console_snapshot` mostly wrap the service call and payload path.
- `dm.console.route_read_snapshot` and `http.request:/api/dm/combat` are route-visible symptoms that include the read path plus scheduling/response effects.

The cheap substeps are ruled out as primary bottlenecks:

- route payload proxy
- combat snapshot copy
- cache check
- tactical merge
- pending prompts
- size proxy

Resource-pools remains closed. Startup-only static fields remains a separate deferred startup outlier.

## Decision

Keep instrumentation commit `e05fb8f`.

Do not authorize direct implementation from this checkpoint.

The next safe latency item is:

`WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint`

Type: planning / implementation decision, not implementation.

Purpose: decide whether a behavior-preserving implementation seam exists inside or immediately around the combat service/read-model composition path now that `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` is the primary remaining actionable span.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.

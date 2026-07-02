# Snapshot/LAN Resource-Pools Hot-Path Cache Smoke Evidence - 2026-07-02

## Scope

This runtime report records a bounded post-implementation docs/evidence checkpoint using an already captured smoke log and debug trace for commit `95bbdf6`.

No app code, tests, logs, browser assets, production configuration, routes, payloads, cache behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture_smoke-server_20260702-123404.log`
- Debug trace: `logs/debug-trace-20260702-123404.jsonl`

The earlier aborted `20260702-104233` start was not used as evidence.

## Smoke Facts

The smoke log records:

- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN sessions connected.
- One LAN session claimed Eldramar.
- The claimed Eldramar session later disconnected while still claimed as Eldramar.

This proves the narrow cache/refinement did not break the captured post-implementation startup/LAN claim path. It does not claim broader gameplay or unclaim coverage.

## Harness Summary

Harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-123404.jsonl
```

Input parse result:

- valid JSON objects: `14,040`
- malformed/non-object lines: `0`

Key latency rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `280` | `6.799 ms` | `842.408 ms` | `24640.335 ms` | `83` | `3` |
| `lan.snapshot.resource_pools` | `280` | `0.092 ms` | `759.372 ms` | `2836.852 ms` | `83` | `2` |
| `lan.snapshot.static_fields` | `280` | `0.090 ms` | `0.264 ms` | `24202.351 ms` | not primary | `1` |
| `dm.tactical.from_lan_snapshot` | `31` | `0.080 ms` | `0.252 ms` | `0.260 ms` | `0` | `0` |
| `dm.console.combat_snapshot` | `53` | `26.693 ms` | `94.884 ms` | `150.560 ms` | `0` | `0` |
| `http.request:/api/dm/combat` | `31` | `79.313 ms` | `1184.073 ms` | `1280.097 ms` | `11` | `4` |

## Tail Evidence

The trace tail shows both the kept fast path and the remaining slow path:

- `resource_pool_mode=dedicated_cache_hit` completed at about `0.081 ms`, `0.097 ms`, `0.079 ms`, and `0.086 ms`
- `resource_pool_mode=ttl_rebuild` completed at about `368.002 ms` and `380.124 ms`

The tail also shows the `ttl_rebuild` slow span nested under `_lan_snapshot` for `lan_tick_idle_cache`, which aligns with the harness summary that `lan.snapshot.resource_pools` still matches `_lan_snapshot` at the `>=250 ms` threshold and nearly matches it at `>=1000 ms`.

## Attribution Decision

The post-implementation evidence proves the new dedicated cache-hit path is cheap, but it does not close the steady-state latency issue.

The strongest recurring actionable hotspot is now the rebuild branch, not the cache-hit branch:

- `dedicated_cache_hit` is sub-millisecond when exercised
- `ttl_rebuild` remains hundreds of milliseconds in the trace tail
- `lan.snapshot.resource_pools` still accounts for the recurring slow `_lan_snapshot` samples

The startup-only `lan.snapshot.static_fields` max remains a separate startup-seed outlier. Its p95 is low, so it should stay deferred outside the `ttl_rebuild` lane.

`dm.tactical.from_lan_snapshot` remains sub-millisecond at p95, and `dm.console.combat_snapshot` stays under `250 ms`, so the fresh evidence does not move the main hotspot away from resource-pools rebuild work.

## Decision

Keep the resource-pools cache refinement from commit `95bbdf6`.

Do not authorize another optimization from this checkpoint.

The next safe work item is:

`WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint`

Type: docs/planning implementation-decision checkpoint.

Purpose: decide whether the remaining `resource_pool_mode=ttl_rebuild` branch has a safe narrow follow-up implementation lever while preserving the kept dedicated cache-hit path and keeping startup static-fields work separate.

## Deferred

Remain deferred until explicitly authorized by a new active work item:

- direct `ttl_rebuild` implementation
- startup static-fields implementation
- broad resource-pools or snapshot/LAN optimization
- cache ownership or cache TTL changes
- snapshot schema or response payload changes
- route registration or route body movement
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, command, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or topology changes
- patching the small smoke bug

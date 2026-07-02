# Snapshot/LAN Hot-Path Targeted Smoke Evidence - 2026-07-02

## Scope

This runtime report records a bounded docs/evidence checkpoint from an already captured targeted smoke run and debug trace.

No app code, tests, logs, browser assets, production configuration, routes, payloads, cache behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture_smoke-server_20260702-090629.log`
- Debug trace: `logs/debug-trace-20260702-090629.jsonl`

## Smoke Facts

The smoke log records:

- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN sessions connected.
- One LAN session disconnected.

The captured smoke tail does not show claim/unclaim events for this run.

## Harness Summary

Harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-090629.jsonl
```

Input parse result:

- valid JSON objects: `18,136`
- malformed/non-object lines: `0`

Key latency rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `491` | `5.428 ms` | `813.985 ms` | `25896.642 ms` | `140` | `10` |
| `lan.snapshot.resource_pools` | `491` | `0.087 ms` | `785.645 ms` | `2823.251 ms` | `140` | `9` |
| `lan.snapshot.static_fields` | `491` | `0.089 ms` | `0.215 ms` | `25435.836 ms` | not primary | not primary |
| `dm.tactical.from_lan_snapshot` | `48` | `0.082 ms` | `0.188 ms` | `0.815 ms` | not primary | not primary |
| `dm.console.combat_snapshot` | `68` | `30.868 ms` | `62.909 ms` | `199.749 ms` | `0` | `0` |
| `http.request:/api/dm/combat` | `48` | `69.298 ms` | `1175.067 ms` | `1258.921 ms` | not primary | not primary |

## Attribution Decision

The targeted trace proves that the new caller/context and subspan attribution is working in live smoke evidence.

The strongest recurring actionable hotspot is `lan.snapshot.resource_pools`. It matches `_lan_snapshot` at the `>=250 ms` threshold and nearly matches the very-slow count at `>=1000 ms`, while the inspected trace snippets show resource-pool rebuild/cached-mode spans under startup, idle cache, LAN tick update, and tactical DM console route contexts.

The large `lan.snapshot.static_fields` max is a startup-seed outlier tied to `lan_startup_seed` with `include_static=true` and `hydrate_static=true`. Its p95 remains low, so it should be separated from steady-state LAN snapshot latency.

The DM tactical extraction span is not the bottleneck in this trace. `dm.tactical.from_lan_snapshot` is sub-millisecond at p95, and `dm.console.combat_snapshot` stays below `250 ms`, while route-visible `/api/dm/combat` p95 is high enough to remain a symptom of nested snapshot work.

## Decision

Direct implementation is not justified from this report alone.

The next safe work item is:

`WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint`

Type: docs/planning implementation-decision checkpoint.

Purpose: decide whether `lan.snapshot.resource_pools` has a narrow behavior-preserving implementation lever, and keep startup-only `lan.snapshot.static_fields` behavior out of the steady-state resource-pools lane.

## Deferred

Remain deferred until explicitly authorized by a new active work item:

- resource-pools implementation
- startup static-fields implementation
- cache ownership, TTL, static hydration, snapshot warm-up, schema, or response payload changes
- route registration or route body movement
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, command, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or topology changes
- patching the small smoke bug

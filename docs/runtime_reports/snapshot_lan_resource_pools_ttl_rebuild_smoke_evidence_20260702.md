# Snapshot/LAN Resource-Pools ttl_rebuild Smoke Evidence - 2026-07-02

## Scope

This runtime report records a bounded post-implementation docs/evidence checkpoint using an already captured smoke log and debug trace for commit `d16a2aa`.

No app code, tests, logs, browser assets, production configuration, routes, payloads, cache behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture_smoke-server_20260702-193152.log`
- Debug trace: `logs/debug-trace-20260702-193152.jsonl`

## Smoke Facts

The smoke log records:

- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN session connected from `10.3.25.162`.
- LAN session claimed Dorian.
- The pasted smoke tail does not show an unclaim or disconnect before `Ctrl+C`.

This proves the narrow `ttl_rebuild` refinement did not break the captured post-implementation startup/LAN claim path. It does not claim broader gameplay, unclaim, disconnect, or browser-smoke coverage.

## Harness Summary

Harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
```

Input parse result:

- valid JSON objects: `57,592`
- malformed/non-object lines: `0`

Key latency rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `_lan_snapshot` | `359` | `59.421 ms` | `247.959 ms` | `24782.192 ms` | `17` | `2` |
| `lan.snapshot.resource_pools` | `359` | `0.309 ms` | `137.346 ms` | `1006.718 ms` | `4` | `1` |
| `dm.tactical.from_lan_snapshot` | `32` | `0.108 ms` | `22.713 ms` | `37.688 ms` | `0` | `0` |
| `lan.snapshot.units` | `359` | `41.883 ms` | `47.763 ms` | `89.288 ms` | `0` | `0` |
| `dm.console.combat_snapshot` | `54` | `839.307 ms` | `2038.109 ms` | `2204.090 ms` | not primary | not primary |
| `http.request:/api/dm/combat` | `30` | `1003.165 ms` | `3454.867 ms` | `4262.795 ms` | not primary | not primary |

The caller/context rows show the steady-state load shape was `212` combatants, `10` players, and `202` monsters.

## Comparison To Prior Evidence

Prior comparator:

- Runtime report: `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_20260702.md`
- Smoke/trace timestamp: `20260702-123404`
- Implementation basis: commit `95bbdf6`

Prior `lan.snapshot.resource_pools` row:

- count `280`
- p50 `0.092 ms`
- p95 `759.372 ms`
- max `2836.852 ms`
- `83` samples at or above `250 ms`
- `2` samples at or above `1000 ms`

New `lan.snapshot.resource_pools` row:

- count `359`
- p50 `0.309 ms`
- p95 `137.346 ms`
- max `1006.718 ms`
- `4` samples at or above `250 ms`
- `1` sample at or above `1000 ms`

Decision: the improvement is material enough to keep `d16a2aa`. The p95 and slow-threshold counts improved even though the new trace was heavier, so the base-normalization reuse layer appears to be paying down the intended `ttl_rebuild` cost.

## Tail Evidence

The trace tail shows the new submode is active:

- `resource_pool_result=ttl_rebuild_base_cache_all_hit`
- `resource_pool_mode=ttl_rebuild`
- `lan.snapshot.resource_pools` around `123.166 ms`
- context `lan_tick_update`
- `212` combatants, `10` players, `202` monsters

This confirms the post-implementation smoke exercised the new base-cache-all-hit path in the heavier steady-state trace.

## Remaining Bottlenecks

Resource-pools is no longer the strongest next optimization candidate from this trace.

The remaining route-visible slow rows are:

- `dm.console.combat_snapshot`: p50 `839.307 ms`, p95 `2038.109 ms`, max `2204.090 ms`.
- `http.request:/api/dm/combat`: p50 `1003.165 ms`, p95 `3454.867 ms`, max `4262.795 ms`.

`lan.snapshot.units` is visible as a moderate substep at p50 `41.883 ms`, p95 `47.763 ms`, and max `89.288 ms`, but it is not the slow-threshold driver in this trace.

Startup-only `lan.snapshot.static_fields` remains separately deferred with max `24337.370 ms`.

## Decision

Keep commit `d16a2aa`.

Do not authorize another immediate resource-pools implementation.

The next safe work item, if latency work continues, is:

`WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint`

Type: docs/evidence planning checkpoint.

Purpose: decide what the remaining DM console combat route/read-model latency represents before any implementation. The checkpoint should preserve the kept resource-pools refinement, keep startup static-fields deferred separately, and avoid changing routes, payloads, cache behavior, WebSockets, queues, production topology, or gameplay behavior.

## Deferred

Remain deferred until explicitly authorized by a new active work item:

- app-code implementation
- tests changes
- log edits
- another resource-pools refinement
- startup static-fields implementation
- broad snapshot/LAN optimization
- cache ownership or cache TTL changes
- snapshot schema or response payload changes
- route registration or route body movement
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, command, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or topology changes
- patching the small smoke bug

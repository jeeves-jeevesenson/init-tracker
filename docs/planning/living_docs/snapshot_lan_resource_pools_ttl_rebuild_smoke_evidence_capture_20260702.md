# Snapshot/LAN Resource-Pools ttl_rebuild Smoke Evidence Capture - 2026-07-02

## Status

Docs/evidence checkpoint completed for implementation commit `d16a2aa`.

This document does not authorize app implementation, latency optimization in this pass, tests, log edits, route movement, payload/schema changes, cache behavior changes, TTL changes, static hydration changes, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, startup static-fields work, small smoke bug fixes, or gameplay/resource semantic changes.

## Decision Summary

Keep commit `d16a2aa`.

The `ttl_rebuild` base-normalization refinement materially improved `lan.snapshot.resource_pools` versus the prior `20260702-123404` comparator:

- p95: `759.372 ms` -> `137.346 ms`
- max: `2836.852 ms` -> `1006.718 ms`
- `>=250 ms`: `83` -> `4`
- `>=1000 ms`: `2` -> `1`

The p50 moved from `0.092 ms` to `0.309 ms`, but both are sub-millisecond and the slow-tail reduction is the important signal.

Do not authorize another immediate resource-pools implementation. The remaining route-visible slow path is now `dm.console.combat_snapshot` and `http.request:/api/dm/combat`, with `lan.snapshot.units` visible as a moderate substep but not a slow-threshold driver in this trace.

Recommended next work item:

`WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint`

Recommended type: docs/evidence planning checkpoint, not implementation.

## Evidence Basis

Evidence run used by this checkpoint:

- implementation commit: `d16a2aa`
- smoke log: `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture_smoke-server_20260702-193152.log`
- debug trace: `logs/debug-trace-20260702-193152.jsonl`
- harness command: `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl`

Smoke facts:

- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN session connected from `10.3.25.162`.
- LAN session claimed Dorian.
- The pasted smoke tail does not show an unclaim or disconnect before `Ctrl+C`.

Harness parse result:

- `57,592` valid JSON objects
- `0` malformed/non-object lines

Key rows:

- `_lan_snapshot`: count `359`, p50 `59.421 ms`, p95 `247.959 ms`, max `24782.192 ms`, `17` samples at or above `250 ms`, `2` samples at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `359`, p50 `0.309 ms`, p95 `137.346 ms`, max `1006.718 ms`, `4` samples at or above `250 ms`, `1` sample at or above `1000 ms`.
- `dm.tactical.from_lan_snapshot`: count `32`, p50 `0.108 ms`, p95 `22.713 ms`, max `37.688 ms`.
- `lan.snapshot.units`: count `359`, p50 `41.883 ms`, p95 `47.763 ms`, max `89.288 ms`.
- `dm.console.combat_snapshot`: count `54`, p50 `839.307 ms`, p95 `2038.109 ms`, max `2204.090 ms`.
- `http.request:/api/dm/combat`: count `30`, p50 `1003.165 ms`, p95 `3454.867 ms`, max `4262.795 ms`.

Startup-only `lan.snapshot.static_fields` remains a separate outlier with max `24337.370 ms`.

The trace tail shows `resource_pool_result=ttl_rebuild_base_cache_all_hit` and `lan.snapshot.resource_pools` around `123.166 ms` in a `212`-combatant state.

## Load Shape Interpretation

The new trace is not a clean apples-to-apples load match with the prior `20260702-123404` evidence. Caller/context rows show steady-state samples with `212` combatants, `10` players, and `202` monsters.

That heavier load shape strengthens the resource-pools keep decision because resource-pools p95 and slow-threshold counts improved despite more combatants. It also cautions against jumping directly from the route-visible DM console numbers to implementation. The next route lane should first be planning/evidence to identify whether the slow work is combat snapshot assembly, nested snapshot work, serialization, request overlap, or a load-shape artifact.

## Planning Questions

1. What did the post-implementation smoke prove still works?

It proved headless tracker startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN connection from `10.3.25.162`, and Dorian claim. It did not prove unclaim or disconnect in the captured tail.

2. Did the `d16a2aa` `ttl_rebuild` refinement improve `lan.snapshot.resource_pools` versus the prior `20260702-123404` evidence?

Yes. Resource-pools p95 fell from `759.372 ms` to `137.346 ms`, `>=250 ms` samples fell from `83` to `4`, max fell from `2836.852 ms` to `1006.718 ms`, and `>=1000 ms` samples fell from `2` to `1`.

3. Is the resource-pools improvement strong enough to keep the implementation?

Yes. The improvement is material and held under heavier load. Keep `d16a2aa`.

4. What slow path remains after resource-pools is improved?

The remaining visible slow path is the DM console combat route/read-model path: `dm.console.combat_snapshot` and `http.request:/api/dm/combat`. `lan.snapshot.units` is now a moderate LAN substep but does not justify direct implementation from this checkpoint.

5. Does the heavier `212`-combatant / `202`-monster load shape change how the evidence should be interpreted?

Yes. It makes the resource-pools improvement more convincing, but it means the next route-visible bottleneck should be investigated by a bounded planning/evidence checkpoint before implementation.

6. Should the next work item be DM console combat route planning/evidence, LAN units planning/evidence, another resource-pools refinement, or pause?

Choose DM console combat route planning/evidence if latency work continues. Pause is still acceptable, but another resource-pools refinement and direct LAN units work are not supported as the next step by this trace.

7. Should startup-only `static_fields` remain deferred separately?

Yes. The static-fields max is still startup-shaped and was not touched.

8. Should the small smoke bug remain deferred as separate bug-capture scope?

Yes. The small smoke bug was not patched and should remain separate.

9. What exact next work item should be recommended?

`WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint`.

## Deferred Scope

Remain deferred until separately authorized:

- broad snapshot/LAN optimization
- another resource-pools implementation
- changing resource-pools behavior or cache behavior
- changing TTLs or the existing one-second resource-pools throttle
- moving cache ownership into `ServerRuntimeFacade`
- route registration changes or route body movement
- broader offload or lower-level tactical/LAN offload
- static hydration changes
- startup-only `lan.snapshot.static_fields` implementation
- snapshot schema or response payload changes
- WebSocket, queue, command semantic, auth, claims, reconnect, hidden-information, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- patching the small smoke bug

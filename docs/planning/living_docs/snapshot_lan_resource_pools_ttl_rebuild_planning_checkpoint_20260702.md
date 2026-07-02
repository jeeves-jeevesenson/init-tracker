# Snapshot/LAN Resource-Pools ttl_rebuild Planning Checkpoint - 2026-07-02

## Status

Docs/planning implementation-decision checkpoint completed. This document does not authorize app implementation by itself, latency optimization in this pass, tests, log edits, route movement, payload/schema changes, cache ownership changes, cache TTL changes, static hydration changes, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, startup static-fields work, small smoke bug fixes, or gameplay/resource semantic changes.

## Decision Summary

The post-implementation smoke evidence is sufficient to justify a future narrow implementation slice for the remaining `resource_pool_mode=ttl_rebuild` latency inside `lan.snapshot.resource_pools`.

The previous implementation at commit `95bbdf6` should be kept. The new dedicated resource-pools cache-hit path is fast when exercised, with trace-tail `resource_pool_mode=dedicated_cache_hit` samples around `0.081-0.097 ms` and harness `lan.snapshot.resource_pools` p50 at `0.092 ms`.

The remaining slow path is the authoritative rebuild branch after the existing one-second resource-pools window expires. In the same post-implementation trace, `resource_pool_mode=ttl_rebuild` appears around `368.002-380.124 ms`, while `lan.snapshot.resource_pools` still accounts for `_lan_snapshot` slow-threshold behavior: both have `83` samples at or above `250 ms`, and resource-pools has `2` of the `_lan_snapshot` `3` samples at or above `1000 ms`.

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation`

Recommended type: narrow implementation.

Recommended goal: reduce rebuild work inside the existing `ttl_rebuild` branch without changing the one-second throttle, cache ownership, cache TTL length, snapshot schema, response payloads, routes, WebSockets, queues, static hydration, startup static-fields behavior, persistence, or resource/gameplay semantics.

## Evidence Basis

Evidence run used by the post-implementation checkpoint:

- smoke log `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture_smoke-server_20260702-123404.log`
- debug trace `logs/debug-trace-20260702-123404.jsonl`
- harness command `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-123404.jsonl`

Harness parse result:

- `14,040` valid JSON objects
- `0` malformed/non-object lines

Key rows:

- `_lan_snapshot`: count `280`, p50 `6.799 ms`, p95 `842.408 ms`, max `24640.335 ms`, `83` samples at or above `250 ms`, `3` samples at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `280`, p50 `0.092 ms`, p95 `759.372 ms`, max `2836.852 ms`, `83` samples at or above `250 ms`, `2` samples at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `280`, p50 `0.090 ms`, p95 `0.264 ms`, max `24202.351 ms`.
- `dm.tactical.from_lan_snapshot`: count `31`, p50 `0.080 ms`, p95 `0.252 ms`, max `0.260 ms`.
- `dm.console.combat_snapshot`: count `53`, p50 `26.693 ms`, p95 `94.884 ms`, max `150.560 ms`.
- `http.request:/api/dm/combat`: count `31`, p50 `79.313 ms`, p95 `1184.073 ms`, max `1280.097 ms`.

The smoke also proves the post-implementation build still started headless, created the debug trace, advertised `/dm` and `/`, hoisted LAN on port `8787`, accepted browser LAN sessions, recorded an Eldramar claim, and recorded disconnect while claimed. It does not claim broader gameplay coverage.

## Current Seam Interpretation

The current resource-pools seam is narrow enough for a future implementation slice:

- `_lan_snapshot()` computes `resource_pool_mode`, times `lan.snapshot.resource_pools`, calls `_lan_resource_pools_payload_for_snapshot()`, emits the low-cardinality cache event, and assigns `snap["resource_pools"]`.
- `_lan_resource_pools_payload_for_snapshot()` preserves the existing one-second rebuild cadence: force rebuild for `include_static=True` or `"resource_pools"` invalidation, rebuild when `now - _lan_resource_pools_last_build >= 1.0`, otherwise reuse cached resource-pools.
- The slow `ttl_rebuild` branch still calls `_player_resource_pools_payload()`.
- `_player_resource_pools_payload()` calls `_load_player_yaml_cache()`, normalizes resource pools for every cached player profile, then augments the payload with temporary condition-derived pools.
- `_normalize_player_resource_pools()` owns formula-derived max values, class defaults, inventory-granted pools, consumable-derived pools, pact magic projection, current-value clamping, and reset metadata.
- `_augment_resource_pools_with_temporary_conditions()` mutates the payload with live temporary Bardic Dice-style pools and `time_left_s`, so this projection must not be treated as a static cached base.
- `_write_player_yaml_atomic()`, deferred YAML writes, `_schedule_player_yaml_refresh()`, `_yaml_players_refresh_cache()`, and `_load_player_yaml_cache()` are the adjacent invalidation/reuse seams that must remain conservative if a future per-player rebuild cache is added.

This is not a route, facade, WebSocket, queue, static hydration, startup static-fields, or production-topology problem.

## Future Implementation Boundary

The safest future slice should preserve the existing one-second resource-pools throttle and avoid changing timing entirely. It should adjust only the amount of work performed by the authoritative rebuild branch when that branch runs.

A safe candidate boundary is:

- Keep `_lan_resource_pools_payload_for_snapshot()` as the owner of rebuild versus reuse decisions.
- Keep `_lan_resource_pools_last_build` and the existing one-second threshold unchanged.
- Keep `include_static=True` and `"resource_pools"` invalidation as authoritative rebuild triggers.
- Keep `_player_resource_pools_payload()` as the authoritative payload builder and keep `snap["resource_pools"]` shape unchanged.
- Add a conservative base-normalization reuse layer inside or directly adjacent to `_player_resource_pools_payload()` that can reuse per-player normalized resource-pool lists only when the underlying player profile cache entry is unchanged.
- Cache only the base normalized profile-derived resource pools. Do not cache temporary condition-derived pools as part of that base.
- On every rebuild, assemble a fresh payload from base entries and run `_augment_resource_pools_with_temporary_conditions()` so live `time_left_s`, expiration pruning, and temporary Bardic Dice-style pools remain current.
- Clear or bypass the base-normalization cache on full player-YAML refresh, force reload, relevant player-YAML writes, `"resource_pools"` invalidation, profile structure/static capability changes, and any uncertain cache key mismatch.
- Preserve fallback-to-cached-resource-pools behavior if authoritative rebuild fails.

If stale-profile detection cannot be made conservative without broadening into unrelated player-YAML ownership, the future implementation item should stop rather than changing resource semantics.

## Planning Questions

1. What did the post-implementation smoke prove about `dedicated_cache_hit`?

It proved the dedicated cache-hit path from commit `95bbdf6` is cheap enough to keep. Trace-tail samples show `resource_pool_mode=dedicated_cache_hit` around `0.081-0.097 ms`, and the overall `lan.snapshot.resource_pools` p50 is `0.092 ms`. The smoke also showed the basic headless/browser/LAN claim path still works for the captured run.

2. What exactly remains slow under `resource_pool_mode=ttl_rebuild`?

The branch that runs after the existing one-second resource-pools rebuild window expires remains slow. It invokes `_player_resource_pools_payload()`, which refreshes/validates the player-YAML cache, normalizes every player's resource pools, derives inventory/consumable/formula/class/pact values, and applies temporary condition projection. In the trace tail, that `ttl_rebuild` branch is around `368.002-380.124 ms`.

3. Is `ttl_rebuild` isolated enough for a narrow future implementation slice?

Yes. The evidence separates cache-hit behavior from rebuild behavior, and the code seam is constrained to `_lan_snapshot()`, `_lan_resource_pools_payload_for_snapshot()`, `_player_resource_pools_payload()`, and adjacent player-YAML invalidation/cache reuse helpers.

4. What correctness boundary would allow `ttl_rebuild` latency reduction without changing resource semantics?

Reduce repeated base normalization work only for unchanged player profiles, while still rebuilding the `resource_pools` payload on the existing cadence and still applying temporary condition projection on every rebuild. The future slice must preserve manual overrides, resource consumption, inventory-granted pools, consumables, formula-derived max values, class defaults, pact magic slots, reset rules, current-value clamping, temporary pools, and payload shape.

5. Is the safest future slice implementation, implementation planning, or more evidence?

The safest next slice is narrow implementation. More evidence is not needed to identify the remaining slow path, and another planning-only pass would mainly restate the same boundary. The future implementation must stop if it cannot conservatively prove stale-profile invalidation.

6. Should the next slice preserve the existing one-second throttle, adjust only rebuild work inside that boundary, or avoid changing timing entirely?

It should preserve the existing one-second throttle and avoid changing timing entirely. The only permitted optimization lever is reducing the synchronous work performed inside the rebuild branch when it already runs.

7. What exact files and behaviors must be protected in any future slice?

Protect app files outside the named `dnd_initative_tracker.py` resource-pools seam. Protect routes, route registration, route bodies, `ServerRuntimeFacade` ownership, snapshot schemas, response payloads, cache ownership outside the legacy seam, cache TTL length, static hydration, startup static-fields behavior, WebSockets, queue behavior, auth/claims/reconnect, hidden-information handling, persistence, launch/lifespan/readiness/shutdown behavior, `UvicornServerHost`, production topology, deploy/restart/SSH/push behavior, and all gameplay/resource rules.

Protect resource-pool semantics specifically: manual overrides, current and max values, resource consumption, resource-pool invalidation domains, inventory-item granted pools, consumable-derived pools, formula-derived max values, class-derived default pools, pact magic slot projection, reset rules, and temporary condition-derived pools including `time_left_s`.

8. What validation should a future implementation slice require?

Use focused validation only:

- `python3 -m py_compile dnd_initative_tracker.py` or the repo virtualenv equivalent.
- Focused unit coverage for unchanged `resource_pools` payload shape, rebuild after existing one-second expiry, cached reuse inside the existing throttle, forced rebuild on `include_static=True`, forced rebuild on `"resource_pools"` invalidation, cache clear/bypass on player-YAML refresh or writes, fallback-to-cache on builder failure, and temporary Bardic Dice-style pools updating without accumulation or stale `time_left_s`.
- Focused facade/snapshot regression tests only if facade-facing behavior is touched.
- `timeout 10s git diff --check`.
- A developer-run targeted smoke/harness comparison can be requested after implementation, but browser smoke remains developer-owned and is not a substitute for unit coverage.

9. Should startup-only `static_fields` remain deferred separately?

Yes. `lan.snapshot.static_fields` remains a startup-only outlier lane. Its p95 is low in the post-implementation evidence, while its max is tied to startup static include behavior. It should not be mixed into this steady-state `ttl_rebuild` slice.

10. Should the small smoke bug remain deferred as separate bug-capture scope?

Yes. The small smoke bug should remain deferred as separate bug-capture scope and should not be patched inside the resource-pools latency lane.

11. What exact next work item should be recommended?

`WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation`

## Deferred Scope

Remain deferred until separately authorized:

- broad snapshot/LAN optimization
- changing the existing one-second resource-pools throttle
- adding TTLs or changing TTL length
- moving cache ownership into `ServerRuntimeFacade`
- route registration changes or route body movement
- broader offload or lower-level tactical/LAN offload
- static hydration changes
- startup-only `lan.snapshot.static_fields` implementation
- snapshot schema or response payload changes
- WebSocket, queue, command semantic, auth, claims, reconnect, hidden-information, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- patching the small smoke bug

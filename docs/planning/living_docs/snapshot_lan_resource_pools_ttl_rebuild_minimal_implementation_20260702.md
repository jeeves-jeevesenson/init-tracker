# Snapshot/LAN Resource-Pools ttl_rebuild Minimal Implementation - 2026-07-02

## Status

Implementation completed as a narrow behavior-preserving refinement inside the legacy-owned resource-pools rebuild seam.

This document does not authorize route changes, route migration, facade-owned cache, TTL changes, static hydration changes, startup static-fields work, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, small smoke bug fixes, or gameplay/resource semantic changes.

## Implemented Shape

The implementation kept `_lan_resource_pools_payload_for_snapshot()` as the rebuild/reuse decision point and kept `_player_resource_pools_payload()` as the authoritative resource-pools payload builder.

The refinement adds base-normalized resource-pool reuse inside `_player_resource_pools_payload()`:

- cached entries are keyed by player name, player profile object identity, and current item/magic-item/consumable registry signatures;
- cached entries contain only profile-derived normalized pool lists;
- each authoritative rebuild assembles a fresh payload from cached or freshly normalized base lists;
- temporary condition-derived pools are appended fresh on every rebuild;
- force rebuilds and player-YAML refresh/write seams clear or bypass the base cache.

The existing one-second resource-pools throttle is unchanged. The dedicated resource-pools payload cache from commit `95bbdf6` is unchanged and remains the holder for payload reuse inside the existing throttle window.

## Trace Labels

The existing `resource_pool_mode` span label continues to distinguish the high-level path:

- `force_rebuild`
- `ttl_rebuild`
- `dedicated_cache_hit`
- `lan_snapshot_cache_hit`
- `cache_miss`

The existing `lan.snapshot.resource_pools.cache` event result now adds low-cardinality TTL rebuild submodes:

- `ttl_rebuild_base_cache_all_hit`
- `ttl_rebuild_base_cache_mixed`
- `ttl_rebuild_base_cache_miss`
- `ttl_rebuild_base_cache_empty`

Fallback labels such as `rebuild_failed_dedicated_cache_hit` and `rebuild_failed_cache_miss` are preserved.

## Correctness Boundary

The base cache intentionally excludes temporary condition-derived pools, including Bardic Dice-style `time_left_s`. Those pools are still projected during every authoritative rebuild and therefore remain live.

Registry signatures are part of the base-cache key because normalized resource pools can depend on item, magic-item, and consumable catalogs. A catalog signature change forces base normalization to run again for otherwise unchanged profiles.

Player-YAML writes, bulk player mutation handling, and full player-YAML refresh clear the base cache conservatively. Force rebuilds caused by `include_static=True` or `"resource_pools"` invalidation also bypass the base cache.

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

## Next Evidence

Recommended next action is developer-run targeted smoke evidence capture with debug trace enabled, followed by the existing latency harness. Use the resulting `lan.snapshot.resource_pools` row and the new TTL rebuild result submodes to decide whether further optimization is justified.

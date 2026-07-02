# Snapshot/LAN Resource-Pools Hot-Path Cache Minimal Implementation - 2026-07-02

## Status

Implementation completed as a narrow legacy-owned cache/refinement at the existing `_lan_snapshot()` / `_player_resource_pools_payload()` seam.

This document does not authorize route changes, route migration, facade-owned cache, TTL changes, static hydration changes, startup static-fields work, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, or gameplay/resource semantic changes.

## Implemented Shape

`_lan_snapshot()` still owns resource-pools snapshot composition. The resource-pools branch now delegates the rebuild/reuse decision to a small helper that preserves the existing conditions:

- rebuild on `include_static=True`
- rebuild while `_last_invalidation_domains` contains `"resource_pools"`
- rebuild once the existing one-second resource-pools window expires
- otherwise reuse cached resource-pools data

The reuse target is now a dedicated tracker-owned `_lan_resource_pools_payload_cache`, with the existing `self._lan._cached_snapshot["resource_pools"]` used only as compatibility backfill/fallback. Fresh authoritative builds still call `_player_resource_pools_payload()` and then update the dedicated cache.

## Trace Evidence

The existing `lan.snapshot.resource_pools` span remains in place.

The span now reports low-cardinality `resource_pool_mode` values:

- `force_rebuild`
- `ttl_rebuild`
- `dedicated_cache_hit`
- `lan_snapshot_cache_hit`
- `cache_miss`

When debug trace is enabled, a companion `lan.snapshot.resource_pools.cache` event reports the actual result, including rebuild fallback values such as `rebuild_failed_dedicated_cache_hit` or `rebuild_failed_cache_miss`.

## Correctness Boundary

The cache does not introduce a new TTL and does not extend the existing one-second rebuild cadence. It only gives `_lan_snapshot()` a stable resource-pools payload holder inside that existing window instead of relying solely on the last full LAN cached snapshot.

The cache is bypassed or reset when correctness is uncertain:

- `include_static=True` forces authoritative rebuild.
- `"resource_pools"` invalidation forces authoritative rebuild.
- one-second expiry forces authoritative rebuild.
- full player-YAML refresh clears the cache and resets the last-build timestamp.

If authoritative rebuild fails, the helper falls back to the dedicated cache or existing LAN snapshot cache so dynamic snapshots keep the `resource_pools` key populated when prior data exists.

## Preserved Behavior

Payload shape and gameplay semantics are preserved because `_player_resource_pools_payload()` remains the only authoritative builder. The implementation did not change normalization, inventory-granted pools, consumable-derived pools, formula-derived max values, class defaults, pact magic slots, temporary Bardic Dice-style pools, resource consumption, refresh rules, rests, spell slot behavior, commands, queues, WebSockets, or routes.

Startup-only `lan.snapshot.static_fields` behavior remains deferred and unchanged.

## Validation

Focused validation passed:

- `.venv/bin/python -m py_compile dnd_initative_tracker.py`
- `timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py` with `78 passed in 1.10s`
- `timeout 10s git diff --check`
- `git status --short`, showing the expected task files plus only known unrelated untracked dirt: `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/`

## Next Evidence

Recommended next action is a developer-run targeted smoke evidence capture using the existing latency harness against a fresh debug trace. The smoke should confirm whether `lan.snapshot.resource_pools` no longer matches `_lan_snapshot` slow-threshold counts under steady-state LAN/browser traffic.

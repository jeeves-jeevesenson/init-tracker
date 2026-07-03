# WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation

Status: Completed

## Goal

Implement the smallest safe behavior-preserving refinement for `resource_pool_mode=ttl_rebuild` inside `lan.snapshot.resource_pools`.

This pass reduced repeated rebuild work only inside the existing legacy-owned `_lan_snapshot()` / `_player_resource_pools_payload()` resource-pools seam. It did not move routes, change route registration, change route bodies, change snapshot schemas or response payloads, change the one-second throttle, add TTLs, move cache ownership into `ServerRuntimeFacade`, change static hydration or startup static-fields behavior, change WebSocket or queue behavior, change persistence, deploy, restart, SSH, push, commit, alter production topology, or patch the small smoke bug.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_planning_checkpoint_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_capture_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `dnd_initative_tracker.py`, limited to `_lan_snapshot()`, `_lan_resource_pools_trace_mode()`, `_lan_cached_resource_pools_payload()`, `_store_lan_resource_pools_payload()`, `_lan_resource_pools_payload_for_snapshot()`, `_player_resource_pools_payload()`, `_normalize_player_resource_pools()`, temporary pool augmentation, player-YAML refresh/write/update seams, and item/consumable registry signature seams used by resource-pool normalization.
- `tests/test_server_runtime.py`, limited to existing resource-pools cache tests and adjacent snapshot regression patterns.

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, routes, browser assets, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_minimal_implementation_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_minimal_implementation_20260702.md`

The active work item copy was created while the task was open and removed after completion.

## Implementation

Added a tracker-owned `_lan_resource_pools_base_cache` for profile-derived normalized resource-pool lists.

`_player_resource_pools_payload()` now:

- loads the existing player-YAML cache as before;
- refreshes the existing item, magic-item, and consumable registry signatures once for the rebuild;
- reuses a cached base normalized pool list only when the player name, profile object identity, and registry signatures are unchanged;
- deep-copies cached base lists into a fresh payload;
- calls `_normalize_player_resource_pools()` for cache misses exactly as before;
- runs `_augment_resource_pools_with_temporary_conditions()` on every rebuild so temporary Bardic Dice-style pools and `time_left_s` remain live and do not accumulate in the base cache.

`_lan_resource_pools_payload_for_snapshot()` still preserves the existing rebuild decision. Force rebuilds still occur for `include_static=True` and `"resource_pools"` invalidation, and TTL rebuilds still occur after the existing one-second window. Force rebuilds clear the base cache before rebuilding. TTL rebuild results now include low-cardinality submodes such as `ttl_rebuild_base_cache_all_hit`, `ttl_rebuild_base_cache_mixed`, and `ttl_rebuild_base_cache_miss` in the existing `lan.snapshot.resource_pools.cache` event result.

Player-YAML full refresh and player-YAML write/update seams clear only the base-normalization cache. They do not clear or alter the dedicated resource-pools payload cache added by commit `95bbdf6`, preserving the previous one-second throttle and fallback/backfill behavior.

## Preserved Behavior

Payload shape and resource semantics are preserved because `_normalize_player_resource_pools()` remains the authoritative base normalizer and `_augment_resource_pools_with_temporary_conditions()` still runs for every authoritative rebuild.

The implementation preserves manual resource-pool overrides, current/max values, current-value clamping, inventory-item granted pools, consumable-derived pools, formula-derived max values, class defaults, pact magic slots, reset rules, gain-on-short metadata, temporary condition-derived pools, fallback-to-cached-resource-pools behavior on build failure, and existing dedicated cache backfill from the LAN cached snapshot.

No route behavior, route registration, route bodies, snapshot schemas, response payloads, cache TTL timing, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, command semantics, auth/claims/reconnect, hidden-information handling, persistence, launch/lifespan/readiness/shutdown behavior, deploy/restart/SSH behavior, production topology, or gameplay/resource rules were intentionally changed.

The small smoke bug was not patched.

## Validation

Focused validation run during this pass:

```bash
.venv/bin/python -m py_compile dnd_initative_tracker.py
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Python compile passed. The first focused pytest run exposed an obvious local naming collision in the new helper, which was fixed inside the same narrow seam. The rerun passed with `80 passed in 1.08s`. Final diff/status command output is recorded in the final agent report.

## Recommended Next Work

Recommended next item: developer-run targeted smoke evidence capture using the existing latency harness against a fresh debug trace before selecting any further optimization.

The smoke should compare `resource_pool_mode=ttl_rebuild_*` result submodes, `resource_pool_mode=dedicated_cache_hit`, and the `lan.snapshot.resource_pools` p95/slow-threshold counts against the prior `20260702-123404` evidence.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item. The completed table now includes this implementation item.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

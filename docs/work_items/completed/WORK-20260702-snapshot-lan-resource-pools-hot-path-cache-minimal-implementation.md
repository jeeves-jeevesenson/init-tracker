# WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation

Status: Completed

## Goal

Implement the smallest safe behavior-preserving resource-pools hot-path cache/refinement at the existing legacy-owned `_lan_snapshot()` / `_player_resource_pools_payload()` seam.

The implementation did not move routes, route bodies, route registration, facade ownership, cache ownership outside the legacy seam, cache TTLs, static hydration, startup static-fields behavior, snapshot schemas, response payloads, WebSocket behavior, queue behavior, gameplay/resource semantics, deploy/restart/SSH behavior, or production topology.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_latency_planning_checkpoint_20260702.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `dnd_initative_tracker.py`, limited to `_lan_snapshot()`, `_player_resource_pools_payload()`, resource-pools cache state, player-YAML invalidation/reset seams, and directly adjacent LAN cached snapshot fallback behavior
- `scripts/snapshot_lan_hot_path_latency_harness.py`, limited to existing span names/output expectations
- `tests/test_server_runtime.py`, limited to existing facade/cache test patterns and focused resource-pools helper tests

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`

The active work item copy was created while the task was open and removed after completion.

## Implementation

Added a tracker-owned `_lan_resource_pools_payload_cache` beside the existing `_lan_resource_pools_last_build` state.

Added helper methods at the legacy seam:

- `_lan_resource_pools_trace_mode()` chooses low-cardinality trace labels.
- `_lan_cached_resource_pools_payload()` reads the dedicated cache first and backfills from `self._lan._cached_snapshot["resource_pools"]` only as compatibility fallback.
- `_store_lan_resource_pools_payload()` stores freshly built payloads.
- `_lan_resource_pools_payload_for_snapshot()` centralizes existing rebuild/reuse behavior for `_lan_snapshot()`.

`_lan_snapshot()` still owns the `lan.snapshot.resource_pools` span and still assigns `snap["resource_pools"]` to the same payload shape produced by `_player_resource_pools_payload()`. The span now records `resource_pool_mode` values such as `force_rebuild`, `ttl_rebuild`, `dedicated_cache_hit`, `lan_snapshot_cache_hit`, and `cache_miss`. When debug trace is enabled, an additional low-cardinality `lan.snapshot.resource_pools.cache` event records the actual result, including rebuild fallback.

The player-YAML full refresh path now clears the dedicated resource-pools payload cache and resets `_lan_resource_pools_last_build`, matching the existing LAN cached snapshot reset.

## Correctness Boundary

The refinement reuses payloads only inside the existing one-second resource-pools throttle window.

It bypasses/rebuilds conservatively when:

- `include_static=True`
- `_last_invalidation_domains` is a `list` or `set` containing `"resource_pools"`
- the existing one-second rebuild window has expired
- the player-YAML refresh path explicitly clears cache state

If an authoritative rebuild fails, the code falls back to the dedicated cache or the existing LAN cached snapshot resource-pools payload, preserving the prior fallback-to-cache behavior rather than stripping `resource_pools` from dynamic snapshots.

## Preserved Behavior

Payload shape and resource semantics are preserved because authoritative rebuild still calls the same `_player_resource_pools_payload()` builder, which still uses the same player-YAML cache, normalization, inventory-granted pools, consumable-derived pools, formula/default pools, pact magic projection, and temporary condition augmentation.

No route behavior, response payloads, snapshot schemas, cache TTLs, static hydration, startup-only `lan.snapshot.static_fields` behavior, WebSocket behavior, queue behavior, command semantics, auth/claims/reconnect, hidden-information handling, persistence, production topology, deploy/restart/SSH behavior, or gameplay/resource rules were intentionally changed.

The small smoke bug was not patched.

## Validation

Required validation commands run during this pass:

```bash
.venv/bin/python -m py_compile dnd_initative_tracker.py
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Results:

- `.venv/bin/python -m py_compile dnd_initative_tracker.py` passed.
- `timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py` passed: `78 passed in 1.10s`.
- `timeout 10s git diff --check` passed.
- `git status --short` showed the expected modified/new task files plus only the known unrelated untracked dirt: `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/`.

## Recommended Next Work

Recommended next work item: developer-run targeted smoke evidence capture using the existing `scripts/snapshot_lan_hot_path_latency_harness.py` against a fresh debug trace.

Purpose: verify whether `lan.snapshot.resource_pools` p95/slow-threshold counts drop in real LAN/browser traffic before selecting any further optimization.

Do not use this implementation as authorization for startup static-fields work, broad snapshot/LAN optimization, route migration, broader offload, facade-owned cache, TTL changes, static hydration changes, WebSocket/queue changes, deploy, restart, SSH, push, or production topology changes.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item. The completed table now includes this implementation item.

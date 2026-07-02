# WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint

Status: Completed

## Goal

Complete a bounded Codex docs/planning implementation-decision checkpoint for the remaining resource-pools `ttl_rebuild` latency isolated by the post-implementation smoke evidence.

This checkpoint decided whether a future narrow implementation slice is justified, what exact boundary it should use, and what behaviors must remain protected. It did not implement a fix, optimize latency, edit app code, edit tests, edit logs, start the server, run smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change route registration, route bodies, launch commands, lifespan/readiness/shutdown behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, cache TTLs, snapshot schemas, response payloads, static hydration, startup static-fields behavior, WebSockets, auth/claims/reconnect, queue behavior, command semantics, persistence, or gameplay/resource semantics.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_capture_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_latency_planning_checkpoint_20260702.md`
- `dnd_initative_tracker.py`, limited to `_lan_snapshot()`, `_lan_resource_pools_trace_mode()`, `_lan_cached_resource_pools_payload()`, `_store_lan_resource_pools_payload()`, `_lan_resource_pools_payload_for_snapshot()`, `_player_resource_pools_payload()`, `_normalize_player_resource_pools()`, `_augment_resource_pools_with_temporary_conditions()`, `_load_player_yaml_cache()`, and directly adjacent player-YAML invalidation/reuse seams.
- `scripts/snapshot_lan_hot_path_latency_harness.py`, limited to `lan.snapshot.resource_pools` and caller/context reporting behavior.

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, tests, browser assets, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_planning_checkpoint_20260702.md`

The active work item copy was created while the checkpoint was open and removed after completion.

## Planning Decision

The future slice is justified as narrow implementation.

The previous implementation at commit `95bbdf6` should be kept because `resource_pool_mode=dedicated_cache_hit` is fast when exercised. The post-implementation evidence isolates the remaining steady-state slow path to `resource_pool_mode=ttl_rebuild` inside `lan.snapshot.resource_pools`, not to the kept dedicated cache-hit path, not to tactical extraction, and not to the startup-only `lan.snapshot.static_fields` outlier.

The recommended next implementation must preserve the current one-second resource-pools throttle and avoid changing timing entirely. It may only reduce the amount of synchronous work performed by the authoritative rebuild branch after that branch is already selected.

## Evidence Summary

The post-implementation harness parsed `14,040` valid JSON objects with `0` malformed/non-object lines.

Key harness rows:

- `_lan_snapshot`: count `280`, p50 `6.799 ms`, p95 `842.408 ms`, max `24640.335 ms`, `83` samples at or above `250 ms`, `3` samples at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `280`, p50 `0.092 ms`, p95 `759.372 ms`, max `2836.852 ms`, `83` samples at or above `250 ms`, `2` samples at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `280`, p50 `0.090 ms`, p95 `0.264 ms`, max `24202.351 ms`.
- `dm.tactical.from_lan_snapshot`: count `31`, p50 `0.080 ms`, p95 `0.252 ms`, max `0.260 ms`.
- `dm.console.combat_snapshot`: count `53`, p50 `26.693 ms`, p95 `94.884 ms`, max `150.560 ms`.
- `http.request:/api/dm/combat`: count `31`, p50 `79.313 ms`, p95 `1184.073 ms`, max `1280.097 ms`.

Trace-tail mode evidence:

- `resource_pool_mode=dedicated_cache_hit` completed around `0.081-0.097 ms`.
- `resource_pool_mode=ttl_rebuild` completed around `368.002-380.124 ms`.

The captured smoke also proved headless startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one Eldramar claim, and disconnect while claimed for the post-implementation build.

## Correctness Boundary

The future implementation should keep `_lan_resource_pools_payload_for_snapshot()` as the rebuild/reuse decision point and keep `_player_resource_pools_payload()` as the authoritative resource-pools payload builder.

Allowed optimization boundary:

- Reuse base normalized resource-pool lists for unchanged player profiles.
- Key or invalidate that base reuse conservatively using player-YAML cache identity, metadata, profile reload, explicit player-YAML writes, and `"resource_pools"` invalidation.
- Assemble a fresh payload on every rebuild and run `_augment_resource_pools_with_temporary_conditions()` every time.
- Keep temporary condition-derived pools out of the cached base layer so `time_left_s`, expiration pruning, and Bardic Dice-style temporary pool projection remain live.

Required preserved behavior:

- `resource_pools` snapshot key presence and payload shape
- manual resource-pool overrides
- current/max values and current-value clamping
- resource consumption and invalidation domains
- inventory-item granted pools
- consumable-derived pools
- formula-derived max values
- class-derived default pools
- pact magic slot projection
- reset rules and gain-on-short metadata
- temporary condition-derived pools, including Bardic Dice-style `time_left_s`
- existing one-second throttle semantics
- include-static forced rebuild behavior
- fallback-to-cached-resource-pools behavior on build failure
- route response payloads and status mapping
- WebSocket, queue, auth, claims, reconnect, hidden-information, persistence, production, and gameplay behavior

## Answers

1. The post-implementation smoke proved `dedicated_cache_hit` is fast enough to keep. Trace-tail hits were about `0.081-0.097 ms`, and the run still covered the basic headless/browser/LAN claim path.
2. The remaining slow path is the authoritative `ttl_rebuild` branch inside `lan.snapshot.resource_pools`, which still calls `_player_resource_pools_payload()` after the existing one-second window expires.
3. Yes. `ttl_rebuild` is isolated enough for a narrow future implementation slice because mode attribution separates it from the fast dedicated cache-hit path and the code seam is limited.
4. The correctness boundary is base-normalization reuse for unchanged player profiles, with live payload assembly and temporary-condition projection on every rebuild.
5. The safest future slice is implementation, not more evidence or another planning pass, with a hard stop if conservative invalidation cannot be preserved.
6. The next slice should preserve the existing one-second throttle and avoid changing timing entirely; only rebuild work inside that boundary should change.
7. Future work must protect the named `dnd_initative_tracker.py` seam boundaries, route/facade ownership, payload/schema shape, cache TTL/throttle semantics, static hydration, startup static-fields behavior, WebSockets, queues, auth/claims/reconnect, hidden information, persistence, production topology, and resource/gameplay semantics.
8. Future implementation validation should include Python compile, focused resource-pools payload/rebuild/cache/invalidation/fallback/temp-pool tests, `timeout 10s git diff --check`, and developer-run smoke/harness comparison only if requested after implementation.
9. Startup-only `lan.snapshot.static_fields` remains deferred separately.
10. The small smoke bug remains deferred as separate bug-capture scope and was not patched.
11. Recommended next work item: `WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation`.

## Recommended Next Work

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation`

Recommended type: narrow implementation.

Recommended goal: reduce repeated synchronous base resource-pool normalization work in the `ttl_rebuild` branch while preserving the existing one-second throttle, legacy-owned cache seam, invalidation behavior, fallback behavior, `resource_pools` payload shape, temporary condition projection, static hydration behavior, startup static-fields deferral, routes, WebSockets, queues, auth/claims/reconnect, persistence, production topology, and all gameplay/resource semantics.

## Deferred Scope

Remain forbidden until separately authorized:

- broad snapshot/LAN optimization
- changing the existing one-second resource-pools throttle
- adding TTLs or changing TTL length
- moving cache ownership into `ServerRuntimeFacade`
- route registration changes or route body movement
- broader `run_in_threadpool` adoption
- lower-level tactical/LAN offload
- static hydration changes
- startup static-fields implementation
- snapshot schema or response payload changes
- snapshot warm-up ownership changes
- WebSocket, queue, command semantic, auth, claims, reconnect, hidden-information, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- patching the small smoke bug

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this `ttl_rebuild` planning checkpoint. The allowed next action is the recommended narrow `ttl_rebuild` minimal implementation item, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item if the small smoke bug remains relevant.

`majorTODO.md` was not inspected or updated because it was outside this task's scope and allowed edit list.

## Validation

Required validation commands:

```bash
git status --short
timeout 10s git diff --check
```

No tests, smoke, server commands, browser commands, deploy commands, production commands, restarts, SSH, pushes, or commits were run by this checkpoint.

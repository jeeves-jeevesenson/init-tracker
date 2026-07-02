# WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint

Status: Completed

## Goal

Complete a bounded Codex docs/planning implementation-decision checkpoint for the resource-pools latency evidence isolated by the targeted smoke trace.

This checkpoint decided whether a future implementation slice is justified, what the smallest safe slice would be, and what behaviors must remain protected. It did not implement a fix, optimize latency, edit app code, edit tests, edit logs, start the server, run browser smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change route registration, route bodies, launch commands, lifespan/readiness/shutdown behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, cache TTLs, snapshot schemas, response payloads, static hydration, WebSockets, auth/claims/reconnect, queue behavior, command semantics, persistence, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence.md`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `dnd_initative_tracker.py`, limited to `_lan_snapshot`, the `lan.snapshot.resource_pools` seam, `_player_resource_pools_payload()`, and directly reached resource-pool normalization helpers needed to interpret the seam
- `server_runtime.py`, limited to `ServerRuntimeFacade.read_snapshot()` and trace-context forwarding
- `docs/planning/living_docs/snapshot_lan_hot_path_targeted_smoke_evidence_capture_20260702.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_planning_checkpoint_20260701.md`

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, tests, browser assets, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_latency_planning_checkpoint_20260702.md`

The active work item copy was created while the checkpoint was open and removed after completion.

## Planning Decision

The targeted smoke evidence is sufficient to justify a future narrow implementation slice for `lan.snapshot.resource_pools`.

The implementation should be narrow, behavior-preserving, and legacy-owned at the existing `_lan_snapshot()` / `_player_resource_pools_payload()` resource-pools seam. It should not move cache ownership into `ServerRuntimeFacade`, broaden offload, change route registration, move route bodies, change payloads/schemas, change static hydration, change cache TTLs, change WebSocket/queue/auth behavior, or mix in startup-only `lan.snapshot.static_fields` work.

## Evidence Summary

The targeted smoke report parsed `18,136` valid JSON objects with `0` malformed/non-object lines.

Key harness rows:

- `_lan_snapshot`: count `491`, p50 `5.428 ms`, p95 `813.985 ms`, max `25896.642 ms`, `140` samples at or above `250 ms`, `10` at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `491`, p50 `0.087 ms`, p95 `785.645 ms`, max `2823.251 ms`, `140` samples at or above `250 ms`, `9` at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `491`, p50 `0.089 ms`, p95 `0.215 ms`, max `25435.836 ms`.
- `dm.tactical.from_lan_snapshot`: count `48`, p50 `0.082 ms`, p95 `0.188 ms`, max `0.815 ms`.
- `dm.console.combat_snapshot`: count `68`, p50 `30.868 ms`, p95 `62.909 ms`, max `199.749 ms`.
- `http.request:/api/dm/combat`: count `48`, p50 `69.298 ms`, p95 `1175.067 ms`, max `1258.921 ms`.

The resource-pools subspan matches `_lan_snapshot` at the `>=250 ms` threshold and nearly matches it at the `>=1000 ms` threshold. That is strong enough to select a resource-pools implementation lane rather than more broad instrumentation.

## Answers

1. The targeted smoke isolated `lan.snapshot.resource_pools` as the recurring actionable `_lan_snapshot` substep across `lan_tick_update`, `dm_console_route_tactical`, `lan_force_state_broadcast`, and startup contexts. The subspan accounts for nearly all recurring p95 and slow-threshold behavior in the targeted trace.
2. The resource-pools evidence is sufficient for a narrow future implementation slice because the substep is isolated and the code seam is constrained to `_lan_snapshot()` and `_player_resource_pools_payload()`.
3. The startup-only `lan.snapshot.static_fields` outlier is separate enough to defer. Its p95 is low and the large max is tied to `lan_startup_seed` startup static include behavior.
4. The smallest safe implementation candidate is a legacy-owned resource-pools hot-path cache/refinement at the existing `_lan_snapshot()` / `_player_resource_pools_payload()` seam, preserving the current one-second throttle, include-static force rebuild, resource-pool invalidation rebuild, fallback behavior, temporary-pool projection, and exact `resource_pools` payload.
5. The safest next slice is implementation, not another planning or evidence pass, provided the implementation remains narrow and stops if it cannot preserve invalidation, throttle, payload, temporary-pool, and gameplay behavior.
6. Future work must protect `dnd_initative_tracker.py` outside the named seam, `server_runtime.py` facade dispatch/trace-context forwarding, route behavior, payload/schema shape, cache ownership outside the legacy seam, cache TTL/throttle semantics, static hydration, snapshot warm-up, WebSockets, queues, auth/claims/reconnect, hidden information, persistence, production topology, deploy/restart/SSH/push behavior, and gameplay behavior.
7. Future validation should use focused py-compile plus focused unit coverage for rebuild, cached reuse inside the current throttle, forced rebuild on `include_static=True`, forced rebuild on `"resource_pools"` invalidation, fallback-to-cache on helper failure, and unchanged payload shape. Facade/snapshot tests are only needed if facade-facing behavior is touched.
8. The small smoke bug remains deferred as separate bug-capture scope and was not patched here.
9. Recommended next work item: `WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation`.

## Protected Behaviors

Any future implementation must preserve:

- `resource_pools` snapshot key presence and payload shape
- manual resource-pool overrides
- resource consumption and resource-pool invalidation domains
- inventory-item granted pools
- consumable-derived pools
- formula-derived max values
- class-derived default pools
- pact magic slot projection
- temporary condition-derived pools, including Bardic Dice-style `time_left_s`
- existing one-second resource-pools throttle semantics
- include-static forced rebuild behavior
- fallback-to-cached-resource-pools behavior on build failure
- route response payloads and status mapping
- WebSocket, queue, auth, claims, reconnect, hidden-information, persistence, production, and gameplay behavior

## Recommended Next Work

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation`

Recommended type: narrow implementation.

Recommended goal: add the smallest behavior-preserving legacy-owned resource-pools cache/refinement at the `_lan_snapshot()` / `_player_resource_pools_payload()` seam to reduce repeated synchronous resource-pool payload work on the LAN snapshot hot path. Do not alter route/facade ownership, payload/schema shape, cache TTLs, static hydration, WebSockets, queues, auth/claims/reconnect, persistence, production topology, or gameplay behavior.

## Deferred Scope

Remain forbidden until separately authorized:

- startup static-fields implementation
- broad snapshot/LAN optimization
- route registration changes or route body movement
- broader `run_in_threadpool` adoption
- lower-level tactical/LAN offload
- facade-owned cache
- cache TTL changes
- static hydration changes
- snapshot schema or response payload changes
- snapshot warm-up ownership changes
- WebSocket, queue, command semantic, auth, claims, reconnect, hidden-information, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- patching the small smoke bug

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this resource-pools latency planning checkpoint. The allowed next action is the recommended narrow implementation item, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item if the small smoke bug remains relevant.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
git status --short
timeout 10s git diff --check
```

No tests, smoke, server commands, browser commands, deploy commands, production commands, restarts, SSH, pushes, or commits were run by this checkpoint.

# DM Console Combat Route Latency Planning Evidence Checkpoint - 2026-07-02

## Status

Docs/evidence planning checkpoint completed for the remaining DM console combat route/read-model latency after commit `d16a2aa`.

This document does not authorize app implementation, latency optimization, tests, log edits, route movement, payload/schema changes, cache behavior changes, TTL changes, static hydration changes, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, startup static-fields work, resource-pools work, small smoke bug fixes, or gameplay/resource semantic changes.

## Decision Summary

Keep `d16a2aa`.

The post-implementation `ttl_rebuild` evidence is accepted because `lan.snapshot.resource_pools` improved materially versus the prior comparator even under a heavier load shape:

- p95 `759.372 ms` -> `137.346 ms`
- `>=250 ms` samples `83` -> `4`
- max `2836.852 ms` -> `1006.718 ms`
- `>=1000 ms` samples `2` -> `1`

The remaining visible slow path is now the DM console combat route/read-model path:

- `dm.console.combat_snapshot`: count `54`, p50 `839.307 ms`, p95 `2038.109 ms`, max `2204.090 ms`
- `_dm_console_snapshot_payload`: count `56`, p50 `901.847 ms`, p95 `2089.417 ms`, max `2317.861 ms`
- `_dm_console_snapshot`: count `51`, p50 `854.435 ms`, p95 `2103.137 ms`, max `2319.635 ms`
- `http.request:/api/dm/combat`: count `30`, p50 `1003.165 ms`, p95 `3454.867 ms`, max `4262.795 ms`

Recommended next work item:

`WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence`

Recommended type: targeted attribution/evidence, not direct implementation.

## Evidence Interpretation

The `212`-combatant / `10`-player / `202`-monster load shape changes the next lane. The remaining latency should be treated as scale/read-model composition evidence, not as a reason to reopen resource-pools, startup static-fields, cache TTLs, route registration, WebSockets, queues, or route migration.

The route/read seam currently does this:

- `GET /api/dm/combat` authenticates, resolves whether tactical data is requested, builds a `RuntimeSnapshotRequest(snapshot_type="dm_console")`, and offloads `runtime.read_snapshot()` through the existing route helper.
- `ServerRuntimeFacade.read_snapshot()` validates the request, resolves `include_tactical`, forwards `_trace_context`, and calls `lan_controller._dm_console_snapshot(...)`.
- `_dm_console_snapshot()` performs a short one-shot cache check and delegates to `_dm_console_snapshot_payload()` when there is no matching cache.
- `_dm_console_snapshot_payload()` wraps `dm_service.combat_snapshot()` in `dm.console.combat_snapshot`, optionally builds tactical data, merges pending prompts, and returns the snapshot.

That means the current trace is strong enough to point at the combat read-model seam, but not strong enough to choose a safe optimization. The trace cannot split the internals of `dm_service.combat_snapshot()` or prove whether response serialization, large tactical responses, or request overlap account for the gap between `_dm_console_snapshot_payload` and `http.request:/api/dm/combat`.

## Span Decision

Primary:

- `dm.console.combat_snapshot` is the best current primary candidate because it is the innermost visible slow span and closely tracks the wrapper spans.

Symptoms/wrappers:

- `_dm_console_snapshot_payload` mostly reflects `dm.console.combat_snapshot` plus optional tactical and pending prompt merge work.
- `_dm_console_snapshot` mostly reflects payload work after cache miss.
- `http.request:/api/dm/combat` is the route-visible symptom and includes response serialization/scheduling beyond the snapshot read.

Not next primary:

- `_dm_tactical_snapshot` remains smaller than the route/read-model total and should not lead the next lane from this evidence.
- `dm.tactical.from_lan_snapshot` is comparatively small: count `32`, p50 `0.108 ms`, p95 `22.713 ms`, max `37.688 ms`.
- `lan.snapshot.units` is visible but bounded: count `359`, p50 `41.883 ms`, p95 `47.763 ms`, max `89.288 ms`.
- Startup-only `lan.snapshot.static_fields` remains a separate startup outlier and should stay deferred.

## Protected Scope For The Next Slice

Any future attribution slice should protect:

- route behavior, route registration, and route bodies
- snapshot schemas and response payload shapes
- cache behavior, cache ownership, cache TTLs, and resource-pools behavior
- static hydration and startup static-fields behavior
- WebSockets, queues, auth, claims, reconnect, hidden-information handling, persistence, and command semantics
- launch commands, readiness/lifespan/shutdown behavior, production topology, deploy/restart/SSH behavior, and gameplay semantics

The small smoke bug should remain separate bug-capture scope and should not be patched inside this latency lane.

## Recommendation

Open `WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence` if latency work continues.

The next task should produce low-cardinality attribution for the DM console combat read-model so a later decision can distinguish:

- combatants/turn-order/battle-log/read-model composition cost
- player versus monster scale effects
- optional tactical response contribution
- response serialization or large response size effects
- overlapping request effects

Do not select direct optimization until the attribution evidence identifies a behavior-preserving seam.

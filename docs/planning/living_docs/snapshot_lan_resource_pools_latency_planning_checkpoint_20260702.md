# Snapshot/LAN Resource-Pools Latency Planning Checkpoint - 2026-07-02

## Status

Docs/planning implementation-decision checkpoint completed. This document does not authorize app implementation, latency optimization, tests, log edits, route movement, payload/schema changes, cache ownership changes, cache TTL changes, static hydration changes, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, or gameplay changes.

## Decision Summary

The targeted smoke evidence is sufficient to justify a future narrow implementation slice for the `lan.snapshot.resource_pools` hot path.

The implementation slice should remain legacy-owned at the `dnd_initative_tracker.py` resource-pools seam inside `_lan_snapshot()` and the directly called `_player_resource_pools_payload()` path. It should not move ownership into `ServerRuntimeFacade`, broaden route offload, change routes, change response payloads, change snapshot schemas, change WebSocket/queue/auth behavior, or mix in startup-only `lan.snapshot.static_fields` work.

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation`

Recommended type: narrow implementation.

Recommended goal: reduce repeated synchronous resource-pool payload work on the LAN snapshot hot path by adding a behavior-preserving legacy-owned resource-pools payload cache/refinement at the existing `_lan_snapshot()` / `_player_resource_pools_payload()` seam. Preserve the current `resource_pools` payload shape, existing one-second rebuild cadence/throttle semantics, resource-pool invalidation behavior, include-static force behavior, temporary-condition projection, manual override/consumption semantics, and all route/facade/WebSocket/queue/gameplay behavior.

## Evidence Basis

The targeted smoke report parsed `18,136` valid JSON objects with `0` malformed/non-object lines.

Key rows:

- `_lan_snapshot`: count `491`, p50 `5.428 ms`, p95 `813.985 ms`, max `25896.642 ms`, `140` samples at or above `250 ms`, `10` samples at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `491`, p50 `0.087 ms`, p95 `785.645 ms`, max `2823.251 ms`, `140` samples at or above `250 ms`, `9` samples at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `491`, p50 `0.089 ms`, p95 `0.215 ms`, max `25435.836 ms`.
- `dm.tactical.from_lan_snapshot`: count `48`, p50 `0.082 ms`, p95 `0.188 ms`, max `0.815 ms`.
- `dm.console.combat_snapshot`: count `68`, p50 `30.868 ms`, p95 `62.909 ms`, max `199.749 ms`.
- `http.request:/api/dm/combat`: count `48`, p50 `69.298 ms`, p95 `1175.067 ms`, max `1258.921 ms`.

`lan.snapshot.resource_pools` matches `_lan_snapshot` exactly at the `>=250 ms` threshold and nearly matches it at the `>=1000 ms` threshold. That makes resource-pool handling the clearest recurring actionable substep behind the steady-state LAN snapshot latency found by the targeted smoke.

## Seam Interpretation

The relevant code seam is narrow:

- `_lan_snapshot()` creates `snap`, computes the existing `resource_pool_mode`, and wraps resource-pool handling in `timed_span("lan.snapshot.resource_pools", ...)`.
- Rebuild mode synchronously calls `_player_resource_pools_payload()`.
- Cached mode currently pulls `resource_pools` from the last LAN cached snapshot.
- `_player_resource_pools_payload()` loads the player YAML cache, normalizes resource pools for each player, then augments the payload with temporary condition-derived pools.
- `ServerRuntimeFacade.read_snapshot()` only forwards whitelisted private trace context into existing builders; it is not the owner of this cache or payload.

This is clear enough for implementation because the expensive substep is isolated to a single snapshot branch and a directly called payload helper. It is not a route-registration, route-body, facade, WebSocket, queue, or startup-static-fields problem.

## Planning Questions

What exactly did the targeted smoke isolate about `lan.snapshot.resource_pools`?

It isolated `lan.snapshot.resource_pools` as the recurring actionable `_lan_snapshot` substep. Its sample count equals `_lan_snapshot`, its p95 nearly equals `_lan_snapshot` p95, its `>=250 ms` count equals `_lan_snapshot`, and its `>=1000 ms` count nearly equals `_lan_snapshot`. The signal appears across `lan_tick_update`, `dm_console_route_tactical`, `lan_force_state_broadcast`, and startup contexts, so it is not only a single route wrapper.

Is the resource-pools latency evidence sufficient for a narrow future implementation slice?

Yes. The evidence and code seam are clear enough for a narrow implementation. Additional broad instrumentation would likely delay the first useful ownership reduction. The future slice must stay limited to behavior-preserving resource-pool payload caching/refinement at the legacy-owned seam.

Is the startup-only `lan.snapshot.static_fields` outlier separate enough to defer?

Yes. `lan.snapshot.static_fields` has a low p95 of `0.215 ms` and a large max tied to the `lan_startup_seed` startup static include path. It should remain deferred and should not be mixed into the steady-state resource-pools implementation lane.

What is the smallest safe implementation candidate?

The smallest safe candidate is a legacy-owned resource-pools hot-path cache/refinement at `_lan_snapshot()` and `_player_resource_pools_payload()`. It should preserve the current one-second throttle, include-static force rebuild behavior, resource-pool invalidation force rebuild behavior, fallback behavior, and the exact `snap["resource_pools"]` payload. A reasonable implementation shape is to stop relying only on the last full LAN snapshot for cached resource pools and introduce a dedicated resource-pools payload cache/helper at the same legacy seam, while keeping rebuild conditions and observable payload semantics unchanged.

Would the safest next slice be implementation, implementation planning, or more instrumentation?

Implementation is the safest next slice, as long as it is narrow and behavior-preserving. More evidence is not required to identify the hot substep, and another planning-only pass would mostly restate the same seam. The implementation item should stop rather than broaden if it cannot preserve invalidation, TTL/throttle, temporary pools, and payload behavior.

What exact files and behaviors must be protected in any future slice?

Protect `dnd_initative_tracker.py` outside the `_lan_snapshot()` resource-pools branch and directly called resource-pool helper path. Protect `server_runtime.py` facade dispatch and `_trace_context` forwarding behavior. Protect `scripts/snapshot_lan_hot_path_latency_harness.py` unless the future item explicitly needs a targeted report enhancement. Protect tests except for focused regression coverage required by the implementation item.

Protect route registration, route bodies, `/api/dm/combat` status mapping and payload shape, LAN snapshot schema, `resource_pools` payload shape, cache ownership outside the legacy seam, cache TTL/throttle semantics, static hydration, snapshot warm-up ownership, WebSocket behavior, queue behavior, command semantics, auth/claims/reconnect, hidden-information behavior, launch/lifespan/readiness/shutdown behavior, `UvicornServerHost`, persistence, production topology, deploy/restart/SSH/push behavior, and gameplay behavior.

Protect resource-pool-specific behavior: manual overrides, resource consumption, resource-pool invalidation domains, inventory-item granted pools, consumable-derived pools, formula-derived max values, class-derived default pools, pact magic slot projection, and temporary Bardic Dice-style condition pools with `time_left_s`.

What validation should a future implementation slice use?

Use focused validation only:

- `python3 -m py_compile dnd_initative_tracker.py` or the repo virtualenv equivalent.
- Focused unit tests covering resource-pool snapshot behavior, including rebuild, cached reuse within the existing throttle, forced rebuild on `include_static=True`, forced rebuild on `"resource_pools"` invalidation domains, fallback-to-cache on helper failure, and unchanged `resource_pools` payload shape.
- Focused facade/snapshot regression tests only if the implementation touches facade-facing snapshot behavior.
- The existing latency harness against the targeted smoke trace may be used as a report comparison if the implementation item explicitly allows reading that trace, but it is not a replacement for unit coverage.

Should the small smoke bug remain deferred as separate bug-capture scope?

Yes. It should remain deferred as separate bug-capture scope. It should not be patched or folded into the resource-pools latency lane.

What exact next work item should be recommended?

`WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation`

## Deferred Scope

Remain deferred until separately authorized:

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

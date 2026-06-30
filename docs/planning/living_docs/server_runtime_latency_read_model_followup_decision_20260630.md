# Server Runtime Latency Read-Model Follow-up Decision - 2026-06-30

## Status

Planning/decision document only. This document does not authorize app implementation, test edits, route migration, cache behavior changes, snapshot builder changes, queue behavior changes, LAN controller changes, Tk changes, WebSocket changes, gameplay changes, browser smoke, server starts, deploys, pushes, or production commands.

## Decision Summary

Selected next slice: cache/read-model refinement.

Exact recommended next work item ID:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision`

The next slice should be a bounded decision/spec pass before code. It should define one narrow, safe refinement for the DM console composite read path rather than immediately adding route-side offload or adopting another read route.

## Why This Slice

The first route-read adoption succeeded behaviorally, but the provided trace shows the adopted route now exposes legacy snapshot build latency through the facade read boundary.

The route wrapper is not the bottleneck. `ServerRuntimeFacade.read_snapshot(dm_console)` delegates directly to `LanController._dm_console_snapshot(include_tactical=...)`, which delegates to `_dm_console_snapshot_payload()`. When tactical payloads are requested, that path also calls `_dm_tactical_snapshot()`, which calls `_lan_snapshot(include_static=False, hydrate_static=False)`.

The trace gives enough evidence to defer another evidence-capture pass. It also shows that adopting more read routes would spread the same hot path before reducing it. Route-side read offload may remain useful later as a transition mitigation, but it does not reduce snapshot build cost and carries concurrency risk around legacy tracker/Tk-owned state.

## Evidence Inspected

Source documents:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_route_read_adoption_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`

Trace and smoke evidence:

- `logs/debug-trace-20260630-164720.jsonl`
- `logs/smoke/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation_smoke-server_20260630-164720.log`

Source sections:

- `server_runtime.py`: `read_snapshot()` only.
- `dnd_initative_tracker.py`: `GET /api/dm/combat`, `_current_request_wants_tactical_map()`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_lan_snapshot()`, and named `_lan_snapshot` call sites.
- `combat_service.py`: `CombatService.combat_snapshot()` only.

## Smoke Evidence

The route-read adoption completion doc records the developer smoke as passed.

The smoke log records:

- Headless tracker startup.
- Debug trace file path: `logs/debug-trace-20260630-164720.jsonl`.
- DM operator surface and player LAN surface URLs.
- LAN session connections.
- A successful claim for Fred.

The smoke log itself did not include detailed route timing. Route timing evidence came from the debug trace.

## GET /api/dm/combat Route Evidence

The trace showed `GET /api/dm/combat` returning HTTP 200 before and after workspace/tactical reads.

Small/no-workspace reads:

- `2.611 ms`, response `465 bytes`
- `2.841 ms`, response `465 bytes`
- `326.690 ms`, response `30831 bytes`

Workspace reads:

- `280.869 ms`, response `184453 bytes`
- `254.325 ms`, response `184453 bytes`
- `1247.723 ms`, response `184547 bytes`
- `1416.111 ms`, response `184713 bytes`
- `1170.187 ms`, response `184713 bytes`
- `1149.322 ms`, response `184877 bytes`
- `1066.479 ms`, response `184877 bytes`
- `112.756 ms`, response `184877 bytes`
- `893.591 ms`, response `184877 bytes`
- `1010.931 ms`, response `184877 bytes`
- `112.959 ms`, response `184877 bytes`

Interpretation: the first route-read adoption is behaviorally viable, but workspace/tactical reads can spend more than 1 second before responding.

## Hot Span Ranking

Route-context hot path for the worst observed `GET /api/dm/combat?workspace` request:

- `http.request`: `1415.720 ms`
- `_dm_console_snapshot`: `1396.260 ms`
- `_dm_console_snapshot_payload`: `1395.968 ms`
- `_dm_tactical_snapshot`: `1305.780 ms`
- `_lan_snapshot`: `1305.254 ms`
- `combat_service.combat_snapshot`: `89.599 ms`

Among the required span families in route context:

- Hottest wrapper: `_dm_console_snapshot`, because it includes the whole DM console composite read.
- Hottest internal source: `_dm_tactical_snapshot` and its `_lan_snapshot` call.
- Lower-order contributor: `combat_service.combat_snapshot`, which was not the dominant source in the slowest route-context examples.

Overall trace notes:

- `_lan_snapshot` is the hottest named snapshot span overall due to non-route startup and standalone spans, including `25739.757 ms`, `2742.220 ms`, `1433.258 ms`, and repeated `385-390 ms` spans.
- `_dm_console_snapshot` route-context spans reached `1396.260 ms`.
- `_dm_tactical_snapshot` route-context spans reached `1305.780 ms`.
- `combat_service.combat_snapshot` route-context spans were usually about `80-175 ms`; the broader trace contained about `269 ms` combat snapshot spans.

## Source Ownership Findings

`GET /api/dm/combat` now builds a `RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": _current_request_wants_tactical_map()})` and returns `ServerRuntimeFacade.read_snapshot(...).data`.

`ServerRuntimeFacade.read_snapshot()` still delegates `dm_console` reads to `LanController._dm_console_snapshot(include_tactical=...)`.

`LanController._dm_console_snapshot()` can use the existing very short-lived `_cached_dm_snapshot` only when no combat or tactical snapshot is supplied and the cache is younger than `0.25` seconds.

`LanController._dm_console_snapshot_payload()` calls `CombatService.combat_snapshot()` and, when tactical inclusion is enabled, calls `InitiativeTracker._dm_tactical_snapshot()`.

`InitiativeTracker._dm_tactical_snapshot()` calls `_lan_snapshot(include_static=False, hydrate_static=False)` and narrows it for DM tactical payload keys.

`_lan_snapshot()` builds a broad LAN/tactical shape: canonical map state, AoEs, aura context, unit payloads, map terrain, structures, ships, resources, and static hydration or cache carryover behavior depending on parameters.

## Decision Against Other Options

Evidence capture: not selected. The existing trace already shows route-level latency, nested snapshot spans, response sizes, and the relative hot path.

Route-side read offload planning: not selected as the immediate next slice. Offload can hide request blocking but does not reduce snapshot cost, and it adds concurrency/thread-safety questions around legacy tracker state.

Another narrow read-route adoption: not selected. More adoption would route additional reads through the facade while preserving the same hot path and latency profile.

Cache/read-model refinement: selected. The evidence points to repeated composite/tactical snapshot construction as the safest next design target.

## Next Work Item Scope

Recommended next work item:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision`

Required goal:

Define one bounded cache/read-model refinement target for `GET /api/dm/combat` and DM console/tactical snapshot hot paths before implementation.

The next decision should specify:

- Whether the first refinement targets DM console composite caching, tactical snapshot reuse, LAN dynamic snapshot reuse, or a narrower combat-vs-tactical route contract.
- Freshness expectations for combat state, tactical map state, pending prompts, resource pools, and static payload hydration.
- Explicit invalidation boundaries.
- Whether the facade continues to delegate cache ownership to `LanController` or introduces any new read-model cache contract.
- Required focused validation for a later implementation.
- Rollback posture and failure behavior.

## Exact Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- App implementation.
- Test edits.
- Route migration.
- More read-route adoption.
- Route-side read offload planning or implementation.
- New instrumentation.
- Cache implementation, cache TTL edits, cache invalidation edits, or facade-owned cache movement.
- Snapshot builder rewrites.
- Queue behavior.
- LAN controller behavior outside the future explicitly scoped refinement.
- Tk behavior.
- WebSocket behavior.
- Gameplay logic.
- Player-command routes.
- Combat mutation routes.
- Rules-aware move.
- AoE create.
- Structures.
- Ships.
- Boarding links.
- Static hydration contract changes.
- Browser smoke.
- Server starts.
- Deploys, pushes, commits, or production commands.

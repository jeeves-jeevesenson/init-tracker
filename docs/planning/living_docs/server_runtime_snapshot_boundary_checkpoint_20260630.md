# Server Runtime Snapshot Boundary Checkpoint - 2026-06-30

## Status

Planning/checkpoint document only. This checkpoint does not authorize app, runtime, route, queue, snapshot, WebSocket, instrumentation, deployment, topology, or browser-smoke changes.

The next lane is snapshot/read-model boundary readiness. Snapshot implementation is explicitly deferred until a separate work item authorizes the contracts, cache ownership, invalidation behavior, validation commands, and implementation scope.

## Current Package Boundary Status

- The `init_tracker_server/` app package exists.
- `server_app.py` remains the compatibility shim for existing app-factory imports.
- `init_tracker_server/runtime.py` exists as the package runtime re-export boundary.
- `server_runtime.py` remains the implementation source for `ServerRuntimeFacade`, runtime command contracts, status constants, command constants, snapshot contracts, and trace contracts.
- Package import realignment is complete: `init_tracker_server/app.py` imports `ServerRuntimeFacade` through `init_tracker_server.runtime` rather than reaching directly into `server_runtime.py`.

Implication: package-local code now consumes the package runtime boundary, but runtime implementation and snapshot ownership have not moved.

## Current Runtime Facade Public Surface

The current facade surface is still command-first and lifecycle-light:

- Command contracts: `RuntimeCommand` and `RuntimeCommandResult`.
- Snapshot contracts: `RuntimeSnapshotRequest` and `RuntimeSnapshotResult`.
- Trace contract: `RuntimeCommandTrace`.
- Status constants: `accepted`, `queued`, `dispatching`, `completed`, `failed`, and `timed_out`.
- Lifecycle/readiness methods: `start()`, `shutdown()`, and `is_ready()`.
- Queue-backed command seam: `submit_command(...)` routes migrated map commands into `_submit_to_lan_queue(...)`, which enqueues a message onto `LanController._actions` and waits for `_action_states` completion.
- Read seam: `read_snapshot(...)` still fails closed with `NotImplementedError("Snapshot reading is not yet implemented.")`.

The package runtime re-export makes these contracts importable from `init_tracker_server.runtime`, but the contracts still live in `server_runtime.py`.

## Queue-Backed Versus Direct Route Families

Queue-backed low-risk tactical/map mutations already migrated through the facade queue adapter:

- Spell color uses the facade command boundary but is not queue-backed.
- Combatant facing.
- Combatant place/reposition.
- Aura overlay enablement.
- AoE remove and AoE move.
- Static map cell updates for obstacles, terrain, and elevation.
- Map settings.
- Background upsert, remove, and order.
- Hazard upsert and remove.
- Feature upsert and remove.

Still-direct higher-risk families documented by the command inventory:

- Rules-aware combatant move.
- AoE create.
- Structures and structure movement/removal.
- Ships and ship maneuvers/weapons/ramming.
- Structure-template instantiation.
- Boarding links.
- Turn/combat mutations.
- HP, condition, temp HP, and combat-state mutation routes.
- Broader WebSocket/LAN action convergence beyond the migrated HTTP route commands.

Decision: direct-route migration is not the next step. The next step should define the snapshot/read-model boundary before moving more high-risk gameplay routes.

## Current Read/Snapshot Ownership

### `_dm_console_snapshot()`

`LanController._dm_console_snapshot(...)` is the route/WebSocket-facing DM snapshot entry point. It decides whether tactical data is included from either `tactical_map_enabled()` or `_current_request_wants_tactical_map()`. If neither a combat snapshot nor a tactical snapshot was supplied, it can reuse `_cached_dm_snapshot` for a very short window when `_cached_dm_snapshot_at` is recent.

That cache behavior is an existing optimization and should be preserved during snapshot-boundary work. A later boundary must not accidentally force every DM console read to rebuild combat and tactical data.

### `_dm_console_snapshot_payload()`

`LanController._dm_console_snapshot_payload(...)` builds the DM console payload. Its combat side prefers a provided `combat_snapshot`; otherwise it calls `self._dm_service.combat_snapshot()`. Its tactical side prefers a provided `tactical_snapshot`; otherwise, when tactical inclusion is enabled, it calls the tracker app's `_dm_tactical_snapshot()`.

The payload also merges pending player-command prompts for DM visibility. The later boundary must account for those prompts instead of treating combat and tactical data as the whole DM console snapshot.

### `CombatService.combat_snapshot()`

`CombatService.combat_snapshot()` owns the combat-focused read model. It reads from the tracker combatant state and builds a DM-focused snapshot with combat flags, round/turn, active/up-next identifiers, turn order, combatants, conditions, state markers, monster resources, and battle log lines. It intentionally avoids the full LAN/tactical snapshot.

This is the current combat-only read model and is the likely source for any future combat-lite snapshot mode.

### `_dm_tactical_snapshot()`

`InitiativeTracker._dm_tactical_snapshot()` owns tactical/map snapshot construction. It calls `_lan_snapshot(include_static=False, hydrate_static=False)`, then narrows that raw LAN snapshot through `_dm_tactical_snapshot_from_lan_snapshot(...)` to map/tactical keys such as grid, obstacles, rough terrain, AoEs, map state, features, hazards, structures, elevation cells, units, turn metadata, boarding links, ships, and aura state.

This is the current tactical/map read model and is the likely source for any future tactical snapshot mode.

### Cached DM Snapshot Prebuild/Reuse

Current `_dm_console_snapshot()` behavior can consume a recently prebuilt `_cached_dm_snapshot` and then clear it. This checkpoint treats that as intentional latency mitigation. Future snapshot-boundary work must define cache ownership and invalidation explicitly rather than bypassing or duplicating this optimization.

## Blocking And Latency Risks

- `ServerRuntimeFacade.submit_command(...)` is synchronous from the route caller's perspective.
- `_submit_to_lan_queue(...)` performs request-thread polling of `LanController._action_states` every 5 ms until completion or timeout, with the default timeout path set to 5000 ms.
- Queue-backed mutation routes commonly return a DM console snapshot immediately after mutation, so the route can pay both queue wait time and snapshot build time before responding.
- Tactical snapshots are hot paths because `_current_request_wants_tactical_map()` includes `/dm/map`, `/dmcontrol`, `/api/dm/map`, `/api/dm/monster-pilot`, and workspace query variants.
- `_dm_tactical_snapshot()` depends on `_lan_snapshot(...)`, so tactical reads remain coupled to the heavier LAN/map state shape.
- Existing `LAN_PERF_DEBUG` timing hooks in `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, and combat service operations are useful evidence hooks, but this checkpoint did not add instrumentation or capture fresh timing data.

Risk posture: a snapshot boundary should reduce unnecessary tactical payload work for combat-only reads and make read-mode choice explicit, but route-side threadpool/offload should be treated only as a transition mitigation if separately authorized.

## Decision Posture

- Snapshot-boundary implementation is not authorized in this checkpoint.
- `read_snapshot()` must remain fail-closed until a separate implementation task defines request/result semantics and validation.
- No route migration, direct-route offload, instrumentation, or gameplay behavior change is authorized here.
- Route-side threadpool/offload may be evaluated later as a transition mitigation only if a separate work item authorizes it and defines rollback/validation.
- Existing cache/prebuild optimization in `_dm_console_snapshot()` must be preserved or deliberately replaced with an equivalent explicit cache contract.

## Prerequisites Before Snapshot Implementation

Before implementing any snapshot boundary, the repo needs a bounded readiness/decision pass that defines:

- `RuntimeSnapshotRequest` semantics: allowed `snapshot_type` values, request params, workspace hints, freshness expectations, and caller identity/admin assumptions.
- `RuntimeSnapshotResult` semantics: success/error shape, data envelope, fail-open/fail-closed behavior, and trace/timing metadata policy if any.
- Combat-only versus tactical snapshot modes: which route/read callers need combat-lite data, which need tactical/map data, and whether DM console payload is a composite mode.
- Fail-open versus fail-closed behavior: whether missing tactical data should omit `tactical_map`, return an empty tactical map, or fail the read.
- Cache ownership: whether the runtime facade owns cache access, delegates to LanController, or only wraps existing `_cached_dm_snapshot` behavior.
- Cache invalidation expectations: which mutations invalidate combat-only data, tactical data, or full DM console composites.
- Validation commands before implementation: focused `py_compile` targets for edited Python files, focused snapshot/facade unit tests, route-level tests only for touched endpoints, and `timeout 10s git diff --check`.

## Explicitly Deferred

- Rules-aware move.
- AoE create.
- Structures.
- Ships.
- Boarding links.
- Route offload.
- Instrumentation.
- Direct gameplay route migration.
- Any implementation of `read_snapshot()`.

## Evidence Ranges Inspected

- `server_runtime.py` lines 1-180: runtime command/snapshot contracts, status constants, command constants, facade readiness methods, and queue adapter setup.
- `server_runtime.py` lines 180-760: queue adapter completion/error mapping, synchronous `submit_command(...)` dispatch, queue-backed command families, spell-color direct-facade exception, and fail-closed `read_snapshot(...)`.
- `dnd_initative_tracker.py` lines 150-190: `_current_request_wants_tactical_map()`.
- `dnd_initative_tracker.py` lines 8388-8548: `_dm_console_snapshot()` and `_dm_console_snapshot_payload()`.
- `dnd_initative_tracker.py` lines 46760-46845: `_dm_tactical_snapshot_from_lan_snapshot()` and `_dm_tactical_snapshot()`.
- `combat_service.py` lines 190-520: `CombatService.combat_snapshot()` shape and immediate post-mutation combat snapshot pattern in `next_turn()`.

## Recommended Next Task

Recommended exact next task:

`WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision`

Type: bounded planning/decision pass.

Goal: define `RuntimeSnapshotRequest` / `RuntimeSnapshotResult` semantics, combat-only versus tactical snapshot modes, fail-open/fail-closed behavior, cache ownership/invalidation expectations, and required validation commands before any snapshot implementation slice.

If that pass determines current timing evidence is insufficient for route-side offload or tactical hot-path prioritization, open a separate narrow evidence-capture pass before implementation. Do not combine evidence capture with implementation.


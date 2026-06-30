# Server Runtime Snapshot Boundary Readiness Decision - 2026-06-30

## Status

Planning/decision document only. This document authorizes a future bounded `ServerRuntimeFacade.read_snapshot()` implementation slice, but it does not itself authorize runtime, app, route, source, test, WebSocket, gameplay, deployment, or browser-smoke changes.

## Current Status

- The package boundary is aligned for the current phase: `init_tracker_server/` exists, `init_tracker_server/runtime.py` is the package runtime re-export boundary, `server_runtime.py` remains the implementation source, and package-local app code imports the facade through the package boundary.
- The queue-backed command seam exists for the already migrated low-risk tactical/map mutation commands.
- `ServerRuntimeFacade.read_snapshot()` still fails closed with `NotImplementedError("Snapshot reading is not yet implemented.")`.
- Read ownership still lives in legacy helpers: `CombatService.combat_snapshot()`, `LanController._dm_console_snapshot()`, `LanController._dm_console_snapshot_payload()`, and `InitiativeTracker._dm_tactical_snapshot()`.
- The next implementation must keep the legacy tracker behind a narrow runtime boundary and must not migrate routes as part of the snapshot implementation.

## Decision Summary

The first `read_snapshot()` implementation should be a narrow facade wrapper around existing legacy read helpers, not a cache relocation, not a route migration, and not a new snapshot builder.

The durable read modes should be:

- `combat`: combat-only DM read model.
- `tactical`: tactical/map read model.
- `dm_console`: route-compatible DM console composite snapshot.

The first implementation should support those modes, fail closed for unsupported modes or unsupported parameters, preserve existing route-visible payload shapes, and leave cache/prebuild ownership inside the existing legacy helper path.

## RuntimeSnapshotRequest Semantics

The existing request contract is:

```python
RuntimeSnapshotRequest(snapshot_type: str, params: Dict[str, Any] = field(default_factory=dict))
```

The future implementation should treat `snapshot_type` as the primary read-mode selector and `params` as explicit caller context. Hidden route context should not be the durable facade contract.

### Snapshot Types

`combat`

- Purpose: return the combat-only DM read model.
- Source: `lan_controller._dm_service.combat_snapshot()`.
- Tactical/map data: not included.
- Static map hydration: not in scope.
- Required params: none.
- Optional params: metadata-only caller context such as `caller` or `workspace`; these must not affect payload shape unless explicitly documented later.
- Invalid params: `include_tactical=True`, `include_static=True`, or `hydrate_static=True` should fail closed because they contradict combat-only semantics.

`tactical`

- Purpose: return the tactical/map read model without the full DM console combat composite.
- Source: `lan_controller.app._dm_tactical_snapshot()`.
- Static map hydration: out of scope for the first implementation. Existing `_dm_tactical_snapshot()` uses `_lan_snapshot(include_static=False, hydrate_static=False)`.
- Required params: none.
- Optional params: metadata-only caller context such as `caller` or `workspace`.
- Invalid params: `include_static=True` or `hydrate_static=True` should fail closed until a separate static-hydration contract is opened.

`dm_console`

- Purpose: return the current DM console composite snapshot shape used by DM routes and DM WebSocket payloads.
- Source: `lan_controller._dm_console_snapshot(include_tactical=<resolved bool>)`.
- Payload includes combat data, pending prompts, and optionally `tactical_map`.
- Tactical inclusion must be explicit through `params["include_tactical"]` or derived from an explicit `params["workspace"]`.
- If both `include_tactical` and `workspace` are present, `include_tactical` wins because it is the direct tactical payload request.
- If neither `include_tactical` nor `workspace` is present, the implementation should fail closed rather than silently consulting hidden request-path globals.

### Workspace And Tactical Preference

Caller context should be passed explicitly.

Allowed workspace values for first implementation:

- `dm`: resolves `include_tactical=False`.
- `combat`: resolves `include_tactical=False`.
- `dmcontrol`: resolves `include_tactical=True`.
- `map`: resolves `include_tactical=True`.
- `map-control`: resolves `include_tactical=True`.
- `monster-pilot`: resolves `include_tactical=True`.

Unknown workspace values should fail closed. Raw request paths such as `/dmcontrol` or `/api/dm/map` should not become a durable facade contract. If a later route migration needs path-based compatibility, the route layer should resolve the path into `workspace` or `include_tactical` before calling the facade.

### Static Map Hydration

Static map hydration is not in scope for the first `read_snapshot()` implementation.

- `include_static=True` and `hydrate_static=True` should fail closed for all first-slice modes.
- The tactical mode should preserve the existing `_dm_tactical_snapshot()` behavior, which intentionally avoids static hydration.
- A later static-hydration contract must define payload size expectations, cache invalidation, and route callers before enabling this.

### Authentication / Caller Role

The first `read_snapshot()` implementation should be treated as a DM/admin read boundary only. Route-level authentication and hidden-information checks remain the route/app responsibility until a separate player/public snapshot contract is designed.

The request may carry metadata such as `caller="dm"` for traceability, but the first implementation should not introduce new auth behavior inside the facade.

## RuntimeSnapshotResult Semantics

The existing result contract is:

```python
RuntimeSnapshotResult(success: bool, data: Dict[str, Any] = field(default_factory=dict))
```

The future implementation should preserve compatibility with this shape while adding defaulted fields only if the implementation task explicitly touches the dataclass. The preferred eventual fields are:

- `success: bool`
- `data: Dict[str, Any]`
- `status: str = STATUS_COMPLETED`
- `message: str = ""`
- `error: Optional[Dict[str, Any]] = None`
- `duration_ms: float = 0.0`
- `metadata: Dict[str, Any] = field(default_factory=dict)`

If the implementation chooses not to extend the dataclass in the first slice, the same semantics must still be asserted in tests through `success`, `data`, and exception/failure behavior.

### Status Values

Read snapshots are synchronous. These status constants apply:

- `completed`: snapshot was produced successfully.
- `failed`: request was invalid, runtime was not ready, a required legacy helper was unavailable, or the legacy helper raised.
- `timed_out`: reserved for a later bounded read timeout/offload implementation. The first implementation should not invent timeout behavior.

These command lifecycle statuses should not be used for read results:

- `accepted`
- `queued`
- `dispatching`

### Payload Shape Expectations

`combat`

- `data` is the direct output from `CombatService.combat_snapshot()`.
- `data` must not contain `tactical_map`.
- Existing combat fields such as `in_combat`, `round`, `turn`, `active_cid`, `up_next_cid`, `turn_order`, `combatants`, and `battle_log` remain legacy-owned.

`tactical`

- `data` is the direct output from `_dm_tactical_snapshot()`.
- Expected keys remain the current tactical subset: `grid`, `obstacles`, `rough_terrain`, `aoes`, `map_state`, `features`, `hazards`, `structures`, `elevation_cells`, `units`, turn metadata, boarding links, ships, and aura state.
- No combat-only response normalization should be introduced in this mode.

`dm_console`

- `data` is the direct output from `_dm_console_snapshot(include_tactical=<resolved bool>)`.
- With tactical disabled, `data` should not include `tactical_map`.
- With tactical enabled, `data["tactical_map"]` should match the legacy tactical payload shape.
- `pending_prompts` must remain present because `_dm_console_snapshot_payload()` currently merges DM-visible pending prompts.

### Error Shape Expectations

Failure must not return partial payloads. On failure:

- `success` is `False`.
- `status` is `failed` unless a later timeout implementation explicitly uses `timed_out`.
- `data` is `{}`.
- `error` should be a dict with at least:
  - `code`: stable machine-readable code.
  - `message`: safe human-readable message.
  - `snapshot_type`: requested snapshot type.
  - `error_class`: exception class when a caught exception caused the failure.

Recommended first-slice error codes:

- `runtime_not_ready`
- `lan_controller_unavailable`
- `tracker_app_unavailable`
- `combat_service_unavailable`
- `snapshot_type_unsupported`
- `snapshot_params_invalid`
- `snapshot_builder_failed`

Stack traces, secrets, request tokens, and raw internal objects must not be included in the result.

### Trace / Timing Fields

Trace and timing should remain result metadata in the first implementation, not route instrumentation.

Allowed result metadata:

- `snapshot_type`
- `include_tactical`
- `workspace`
- `source`
- `duration_ms`

The first implementation should not emit new debug events, route timing logs, browser-visible timing fields, or production instrumentation unless a separate instrumentation work item authorizes it.

## Fail Behavior Decision

`read_snapshot()` currently remains fail-closed and unimplemented. The future implementation should keep fail-closed semantics after implementation.

Fail closed when:

- The facade is not ready.
- `lan_controller` is unavailable.
- The required legacy app/helper/service reference is unavailable.
- `snapshot_type` is unknown.
- Params request unsupported static hydration.
- Params are contradictory to the requested mode.
- The legacy builder raises.

Fail-open/cache fallback:

- No new facade-owned fail-open behavior is allowed in the first implementation.
- No stale snapshot fallback is allowed when the requested builder fails.
- The only allowed cache reuse is the existing short-lived one-shot `_cached_dm_snapshot` behavior inside `_dm_console_snapshot()`.
- If `_dm_console_snapshot()` chooses to use or clear its existing cache, the facade must treat that as delegated legacy behavior, not as facade cache ownership.

Before runtime readiness:

- `read_snapshot()` should not produce a payload before readiness.
- The preferred future behavior is a failure result with `runtime_not_ready`; if the first implementation preserves exception-style failure for compatibility, tests must assert that it fails closed with no payload.

When legacy references are unavailable:

- Missing `lan_controller`, missing `lan_controller.app`, missing `_dm_service`, or missing snapshot builder methods must fail closed with no payload.
- The implementation should not synthesize empty combat or tactical payloads to keep routes alive.

## Cache / Prebuild Ownership Posture

The existing cached DM snapshot reuse optimization must be preserved.

First implementation posture:

- `ServerRuntimeFacade` should not own a snapshot cache.
- `ServerRuntimeFacade` should not relocate `_cached_dm_snapshot` or `_cached_dm_snapshot_at`.
- `ServerRuntimeFacade` should not introduce new invalidation hooks.
- `dm_console` mode should delegate to `_dm_console_snapshot(...)` so the existing short-lived cache/prebuild optimization remains intact.
- `combat` and `tactical` modes should call their existing legacy builders directly and should not add facade-side cache behavior.

Invalidation assumptions:

- Current invalidation/prebuild behavior remains legacy-owned.
- Combat mutations are assumed to affect `combat` and `dm_console` freshness.
- Tactical/map mutations are assumed to affect `tactical` and `dm_console` freshness.
- Pending player-command prompt changes are assumed to affect `dm_console` freshness.
- A later cache-owner task must make those invalidation domains explicit before moving or expanding cache behavior.

What must not change in the first implementation:

- No cache relocation.
- No cache TTL change.
- No change to one-shot cache clearing behavior.
- No new static hydration cache.
- No change to mutation/broadcast invalidation behavior.
- No route-visible payload shape change.

## Later Implementation Boundary

Narrowest allowed implementation files for the later slice:

- `server_runtime.py`
- `init_tracker_server/runtime.py` only if new snapshot constants/result fields must be re-exported.
- `tests/test_server_runtime.py`
- Work-item and living-doc files needed to record completion.

The later implementation should stop if it requires edits to:

- `init_tracker_server/app.py`
- `server_app.py`
- `dnd_initative_tracker.py`
- `combat_service.py`
- route handlers
- WebSocket/LAN queue behavior
- gameplay mutation helpers

Likely first implementation path:

1. Add explicit snapshot type constants in `server_runtime.py`.
2. Re-export those constants through `init_tracker_server/runtime.py` if the package boundary needs them.
3. Optionally add defaulted result fields to `RuntimeSnapshotResult` without breaking existing construction.
4. Implement `ServerRuntimeFacade.read_snapshot(...)` as a small dispatcher.
5. Delegate `combat` to `lan_controller._dm_service.combat_snapshot()`.
6. Delegate `tactical` to `lan_controller.app._dm_tactical_snapshot()`.
7. Delegate `dm_console` to `lan_controller._dm_console_snapshot(include_tactical=<resolved bool>)`.
8. Add focused tests proving success, fail-closed behavior, package re-export behavior, cache delegation posture, and unsupported static hydration failure.

Public behavior that must remain unchanged:

- Existing routes must continue calling existing helpers until a separate route migration is opened.
- Existing DM/player/LAN/Tk/WebSocket behavior must not change.
- Existing snapshot payload shapes must not be normalized.
- Existing cache/prebuild behavior must not be moved.
- Existing command queue behavior and command traces must not change.

## Validation Plan For Later Implementation

Required validation for the later implementation slice:

```bash
git status --short
timeout 10s git diff --check
timeout 10s python3 -m py_compile server_runtime.py init_tracker_server/runtime.py
timeout 30s python3 -m unittest tests.test_server_runtime.ServerRuntimeFacadeTests
```

If the package boundary is touched, add a scoped import/app-factory validation:

```bash
timeout 10s python3 - <<'PY'
import init_tracker_server.runtime as runtime
import server_runtime

assert runtime.ServerRuntimeFacade is server_runtime.ServerRuntimeFacade
assert runtime.RuntimeSnapshotRequest is server_runtime.RuntimeSnapshotRequest
assert runtime.RuntimeSnapshotResult is server_runtime.RuntimeSnapshotResult
print("runtime snapshot import boundary ok")
PY
```

No browser smoke is authorized for the first snapshot implementation unless a later task explicitly authorizes it. No broad tests should be run.

## Explicitly Deferred

- Direct-route migration.
- Route offload.
- Route instrumentation.
- AoE create.
- Rules-aware move.
- Structures.
- Ships.
- Boarding links.
- Gameplay mutation semantics.
- Static map hydration.
- Snapshot cache relocation.
- WebSocket/event publication boundary changes.
- Browser smoke.

## Recommended Next Task

Recommended exact next task:

`WORK-20260630-runtime-facade-read-snapshot-minimal-implementation`

Reason: this decision defines enough request/result, mode, failure, cache, boundary, and validation semantics to proceed directly to a minimal implementation slice with focused tests included. A separate tests-only task would either leave intentionally failing tests in the repo or duplicate most of the implementation task scope. The next slice should still write the contract tests first inside the implementation pass, then implement only the minimal facade wrapper needed to make them pass.


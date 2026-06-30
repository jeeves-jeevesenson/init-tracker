# Server Runtime Route-Read Adoption Decision - 2026-06-30

## Status

Planning/decision document only. This document authorizes a future bounded route-read adoption implementation slice but does not itself modify route handlers, gameplay logic, or test code.

## Current Status

- **Package Boundary Aligned:** The `init_tracker_server/` package exists, and the runtime re-export boundary in `init_tracker_server/runtime.py` is fully wired. `server_runtime.py` remains the implementation source.
- **Minimal `read_snapshot()` Complete:** `ServerRuntimeFacade.read_snapshot()` is implemented and supports `combat`, `tactical`, and `dm_console` snapshot modes. It is fully validated and covered by focused unit tests.
- **Routes Use Legacy Helpers:** Route handlers in `dnd_initative_tracker.py` (e.g., `GET /api/dm/combat` and migrated mutation endpoints) still call the legacy `_dm_console_snapshot()` helper directly.
- **Direct Gameplay Route Migration Deferred:** Rules-aware move, AoE creation, structures, ships, boarding links, and turn mutations remain deferred.

## Route-Read Adoption Candidates

### Safe First Candidate Family

1. **Pure Read Endpoints:** `GET /api/dm/combat` is a pure read endpoint returning the composite DM console snapshot via `_dm_console_snapshot()`. It has no mutation side effects, making it the safest starting point.
2. **Queue-Backed Mutation Endpoints:** Endpoints that are already migrated to the facade's queue-backed command seam (e.g., `POST /api/dm/map/combatants/{cid}/facing`, `POST /api/dm/map/combatants/{cid}/place`, and map hazard/feature/background operations) currently return `{"ok": True, "snapshot": _dm_console_snapshot()}`. Adopting `read_snapshot()` here aligns their write and read boundaries under the facade.

### High-Risk Excluded Routes

Direct gameplay mutation routes (e.g., rules-aware combatant move, AoE create, ship maneuvers, and direct health/status mutations) are excluded from read adoption. Because their write paths are not yet migrated to the facade, updating their read behavior prematurely introduces unnecessary coordination risk.

## Adoption Strategy

### Snapshot Mode and Parameters

The first implementation slice will swap the response snapshot reads to:
- **Snapshot Type:** `dm_console`
- **Params:**
  - `include_tactical`: Derived explicitly via `_current_request_wants_tactical_map()`.
  - `workspace`: Left as optional context metadata or derived from route context where appropriate.

### Route-Layer Fallback / Fail-Closed Posture

- **Fail-Closed:** If `read_snapshot()` returns `success=False` or raises an exception, the route handler must fail closed.
- **HTTP Mapping:**
  - If the failure is due to readiness, map it to `HTTPException(status_code=503, detail="Service Unavailable")`.
  - If it is a builder or runtime failure, map it to `HTTPException(status_code=500, detail="Failed to read snapshot")`.
- **No Legacy Fallback:** The route handler must not fall back to direct legacy helpers or return partial/synthesized payloads on facade failure.
- **Payload Compatibility:** The route response must preserve the exact dictionary structure returned by `read_snapshot(dm_console).data` to prevent breaking frontend clients.

## Evidence Needs

- **Ready Now:** The implementation of `read_snapshot()` maps cleanly to the same underlying legacy helper methods, preserving all cache optimizations and query-path context.
- **Decision:** No preliminary evidence-capture pass (e.g., timing or performance telemetry logs) is needed before proceeding to a minimal route-read adoption slice. We can move straight to the minimal implementation.

## Later Implementation Boundary

### Allowed Files to Edit

- `dnd_initative_tracker.py` (only targeted route handlers).
- `tests/test_dnd_initative_tracker.py` (focused integration/route test updates).
- Ledger and work item files.

### Forbidden Files/Scope

- `server_runtime.py` (already implemented).
- `combat_service.py`.
- `init_tracker_server/app.py`.
- Direct gameplay mutation paths or WebSocket/LAN event structures.

### Target Route for First Slice

The safest first route is `GET /api/dm/combat`. Its implementation will swap the legacy call:
```python
return _dm_console_snapshot()
```
to a facade invocation:
```python
request = RuntimeSnapshotRequest(
    snapshot_type="dm_console",
    params={"include_tactical": _current_request_wants_tactical_map()}
)
result = self._runtime.read_snapshot(request)
if not result.success:
    raise HTTPException(status_code=500, detail="Failed to read combat snapshot.")
return result.data
```

### Focused Route Tests

Add route-level integration tests asserting:
1. Success returns the correct `dm_console` dictionary.
2. Failure maps to HTTP 500/503 and returns no partial state.
3. Appropriate parameters (`include_tactical`) are correctly supplied.

### Validation Commands

```bash
git status --short
timeout 10s git diff --check
timeout 10s python3 -m py_compile dnd_initative_tracker.py
```

## Explicitly Deferred

- Rules-aware move.
- AoE create.
- Structures, ships, and boarding links.
- Route-side threadpool/async offload.
- New telemetry/instrumentation.
- Gameplay mutation changes.

## Recommended Next Task

**Selected Task:** `WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation`

**Reason:** The facade boundary is fully prepared, tested, and ready to accept route traffic. A separate evidence-capture pass is unnecessary because there are no behavior or performance changes introduced by this delegation. Proceeding to a minimal implementation slice for `GET /api/dm/combat` is the most direct and safest way to prove route-read adoption.

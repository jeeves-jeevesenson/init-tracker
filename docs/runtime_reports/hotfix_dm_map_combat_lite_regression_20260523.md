# Runtime Report: Hotfix DM Map / DM Control Loading Regression

- **Date**: 2026-05-23
- **Hotfix Target**: Restore `/dm/map` and `/dmcontrol` map functionality while preserving combat-lite latency optimizations for normal combat loops.

---

## 1. Root Cause Analysis
During the playability pass on 2026-05-22, the tactical map build was disabled by default when `INIT_TRACKER_ENABLE_TACTICAL_MAP=false` to optimize combat loops. However, the gating was too broad, affecting the DM Map Workspace (`/dm/map`) and the dedicated DM Control page (`/dmcontrol`).

While the `/dm/map` workspace was hotfixed by forcing tactical snapshots on its path, the `/dmcontrol` surface remained blank/broken. `/dmcontrol` is a dedicated, map-first monster encounter control cockpit. Unlike `/dm`, `/dmcontrol` does not use WebSockets to sync state, but instead polls `/api/dm/combat` every 2 seconds via standard `fetchState()` HTTP GET requests.

Because `/api/dm/combat` is combat-lite by default, `/dmcontrol` received combat-lite state payloads that completely lacked the `tactical_map` grid and coordinate markers, rendering its active tactical map unusable.

---

## 2. Restored Workspace-Aware Contract
We implemented a surgical, workspace-aware subscription and routing model covering both `/dm/map` and `/dmcontrol`:
1. **Combat-Lite Paths** (`/api/dm/combat`, `/api/dm/combat/next-turn` when loaded without query params) remain strictly combat-lite and do not construct the `_dm_tactical_snapshot` in the HTTP response.
2. **Explicit Map / Control Workspaces**:
   - The map workspace (`/dm/map`), explicit map mutation API routes (`/api/dm/map/*`), and DM control workspace (`/dmcontrol`) always load with tactical payloads.
3. **HTTP Query-Parameter Context Routing**:
   - Updated the FastAPI HTTP middleware to capture request query strings in the `_CURRENT_REQUEST_PATH` ContextVar (e.g. `/api/dm/combat?workspace=dmcontrol`).
   - `_current_request_wants_tactical_map()` checks for `"workspace=dmcontrol"` or `"workspace=map"` in the ContextVar path.
   - Any fetch from the `/dmcontrol` frontend now appends `?workspace=dmcontrol` to ensure the server returns the tactical map in its snapshots.
4. **WebSocket Session-Level Subscriptions**:
   - Connections to `/ws/dm` specify `workspace=map` or `workspace=dmcontrol` in their query parameters.
   - The server registers the connection's map-subscription status in `LanController._dm_ws_is_map`.
   - The websocket also supports a `{"action": "subscribe_map"}` command to transition a connection to a map-subscribed connection on demand.
5. **Smart Broadcast Updates**: Background state broadcasts (`_lan_force_state_broadcast`) only build the heavy tactical map snapshot if the action was a direct map mutation or if at least one active WebSocket client is currently subscribed/on a map-capable workspace.

---

## 3. Implementation Details
- **FastAPI Middleware**: Modified `set_current_request_path_middleware` to set `_CURRENT_REQUEST_PATH` to the full path + query parameters:
  ```python
  full_path = request.url.path
  if request.url.query:
      full_path += f"?{request.url.query}"
  ```
- **wants_tactical Check**: Updated `_current_request_wants_tactical_map()` to check if the path is `/dmcontrol` or the query contains `workspace=dmcontrol`.
- **WebSocket Query Param Validation**: Updated `ws_dm_endpoint` to register `dmcontrol` and `map-control` as map-subscribed WebSocket clients:
  ```python
  is_map_client = (workspace in ("map", "dmcontrol", "map-control"))
  ```
- **DMControl Frontend API URL Updates**:
  Updated all API endpoints in `assets/web/dmcontrol/index.html` to append `?workspace=dmcontrol` (or `&workspace=dmcontrol` if query params already existed):
  - `const API_COMBAT = '/api/dm/combat?workspace=dmcontrol';`
  - `/api/dm/combat/start?workspace=dmcontrol` and `/api/dm/combat/next-turn?workspace=dmcontrol` in `handleCombatControl`.
  - `/api/dm/map/combatants/${cid}/move?workspace=dmcontrol` in `executeMove`.
  - `/api/dm/combat/long-rest?workspace=dmcontrol` in `handleLongRest`.
  - `/api/dm/monster-capabilities/${actorCid}/execute?workspace=dmcontrol` in `activateModifier`, `prepareLocalResolutionPreview`, and `startSequence`.
  - `/api/dm/monster-capabilities/${actorCid}/resolve-targets?workspace=dmcontrol` in `applyLocalResolutionResults`.

---

## 4. Verification Results
We added/expanded our custom integration unit tests in `tests/test_dm_tactical_map_routes.py`:
1. `test_dmcontrol_endpoint_and_workspace_queries_force_tactical_snapshot` — verifies that `/dmcontrol` route, `/api/dm/combat?workspace=dmcontrol` GET polling, and `/api/dm/combat/next-turn?workspace=dmcontrol` POST actions all force the inclusion of `tactical_map` under combat-lite defaults.
2. `test_ws_dm_endpoint_dmcontrol_workspace_query_param` — verifies that WebSocket connections from `dmcontrol` query-parameter sessions receive tactical payloads successfully on startup.

All code is fully validated, compliant with python and JavaScript node compilation gates, and fully operational.

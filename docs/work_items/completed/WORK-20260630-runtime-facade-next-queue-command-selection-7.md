# WORK-20260630-runtime-facade-next-queue-command-selection-7

## Status

Completed

## Title

Runtime facade next queue command selection 7

## Goal

Select the next low-risk production command to route through the `ServerRuntimeFacade` queue adapter after facing, aura overlays, place/reposition, AoE removal, AoE move, obstacle cell toggle, and terrain cell toggle. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260630-runtime-facade-queue-command-terrain-cell](../completed/WORK-20260630-runtime-facade-queue-command-terrain-cell.md)
- [WORK-20260630-runtime-facade-next-queue-command-selection-6](../completed/WORK-20260630-runtime-facade-next-queue-command-selection-6.md)

---

## Evidence Report

We evaluated the following candidates from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/elevation/cell` (Set Map Cell Elevation)
* **Route Location & Handler Shape:** `dm_set_map_elevation` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6231-L6256) calling `self.app._dm_set_elevation_on_map(col=col, row=row, elevation=payload.get("elevation"))`.
* **Existing `_actions` Mapping:** No. Will need to define a new action/message type `set_elevation`.
* **Payload Complexity:** Very low.
  ```json
  {
    "col": int,
    "row": int,
    "elevation": float
  }
  ```
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "col": int,
    "row": int,
    "elevation": float,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Very low. Mutates only the `elevation_cells` dictionary on the MapState via `_mutate_canonical_map_state`.
* **Gameplay/State Risks:** **Low**. Cell elevation is a presentation/visualization metric on cells. Pathfinding (`_lan_shortest_cost`) and movement speed budgets do not depend on cell elevation. There are no hazard triggers, mounts/riders interactions, or HP changes associated with changing cell elevation. Running it on the Tk main thread resolves concurrent state mutation issues safely.
* **Expected Focused Tests:**
  - `test_set_elevation_command_success` (execution, queue wait telemetry, trace validation)
  - `test_set_elevation_command_validation_failure` (error validation on coordinates or non-numeric elevation)
  - `test_set_elevation_route_level_behavior_mapping` (route-to-facade delegation)

### 2. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Location & Handler Shape:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4666-L4694) calling `self.app._dm_move_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **Payload Complexity:** Low.
  ```json
  {
    "col": int,
    "row": int
  }
  ```
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "cid": int,
    "col": int,
    "row": int,
    "spent_ft": int,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** High. Checks boundaries and obstacles, resolves rider/mount positioning, calculates shortest cost, updates token position, applies environmental move damage, handles environment triggers, handles sneak hidden movement, and rebuilds the initiative table.
* **Gameplay/State Risks:** **High**. Highly coupled with remaining movement speed budgets, pathfinding, environmental hazards, mounts/riders follow logic, and turn enforcement. Can deal damage or prompt reaction dialogs which could block or timeout the queue thread. Too risky for this phase.
* **Expected Focused Tests:**
  - `test_dm_move_combatant_success`
  - `test_dm_move_combatant_blocked_path`
  - `test_dm_move_combatant_insufficient_movement`

### 3. `POST /api/dm/map/aoes` (Create map AoE)
* **Route Location & Handler Shape:** `dm_create_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6333-L6353) calling `self.app._dm_create_aoe_on_map(payload)`.
* **Existing `_actions` Mapping:** No.
* **Payload Complexity:** Medium. Requires shape, geometry parameters, radius, color, and attached caster ID.
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "aid": int,
    "aoe": dict,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Medium. Instantiates a new AoE object and adds it to the active map state.
* **Gameplay/State Risks:** **Medium**. Modifies active AoEs on the board, but doesn't immediately block movement speed budgets or turn states. Slightly more complex state/geometry mutation than elevation cells.
* **Expected Focused Tests:**
  - `test_create_aoe_command_success`
  - `test_create_aoe_invalid_geometry`

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST .../elevation/cell` (Set Elevation)** | No | Yes | **Low** | Updates only the elevation cells dictionary. No gameplay/movement rules or complex dependencies. Runs on Tk thread. |
| **`POST .../aoes` (Create AoE)** | No | Yes | **Medium** | Moderately complex payload and active board effects/geometry. |
| **`POST .../move` (Rules Move)** | Yes | No | **High** | Highly coupled with movement budgets, hazards, reactions, mounts. |

We recommend migrating **`POST /api/dm/map/elevation/cell` (Set Map Cell Elevation)** next.

By migrating the cell elevation command, we route another concurrent FastAPI request handler through the thread-safe Tk main thread queue adapter with minimal risk, mirroring the successful migrations of obstacle cell and terrain cell toggle commands.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-elevation-cell`

### Exact route/command to migrate
- Route: `POST /api/dm/map/elevation/cell`
- Command: `COMMAND_SET_ELEVATION = "set_elevation"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch)
- `dnd_initative_tracker.py` (Update `dm_set_map_elevation` route to delegate via facade, handle callback mapping to store `elevation_result` under `_action_states`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_SET_ELEVATION` success, validation failures, and route mappings)

### Files explicitly out of scope
- `player_command_contracts.py`
- `player_command_service.py`
- `dnd_initative_tracker.py` combatant movement or spellcasting logic.

### Focused validation commands for that future slice
```bash
python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
.venv/bin/python -m unittest tests/test_server_runtime.py
git status --short
timeout 10s git diff --check
```

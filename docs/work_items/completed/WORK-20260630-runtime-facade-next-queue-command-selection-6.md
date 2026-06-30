# WORK-20260630-runtime-facade-next-queue-command-selection-6

## Status

Completed

## Title

Runtime facade next queue command selection 6

## Goal

Select the next low-risk production command to route through the `ServerRuntimeFacade` queue adapter after facing, aura overlays, place/reposition, AoE removal, AoE move, and obstacle cell toggle. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260629-runtime-facade-queue-command-obstacle-cell](../completed/WORK-20260629-runtime-facade-queue-command-obstacle-cell.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-5](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-5.md)

---

## Evidence Report

We evaluated the following candidates from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/terrain/cell` (Toggle Map Terrain Cell)
* **Route Handler / Path:** `dm_set_terrain_cell` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5613-L5656) calling `self.app._dm_set_terrain_on_map(...)`.
* **Existing `_actions` Mapping:** No. Will need to define a new action/message type `set_terrain`.
* **New Action Type Required:** Yes.
* **Payload Shape:**
  ```json
  {
    "col": int,
    "row": int,
    "is_rough": bool,
    "movement_type": str,
    "color": "Optional[str]",
    "label": "Optional[str]"
  }
  ```
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "col": int,
    "row": int,
    "is_rough": bool,
    "movement_type": str,
    "color": "Optional[str]",
    "label": "Optional[str]",
    "snapshot": dict
  }
  ```
* **Gameplay/State Risks:** **Low**. Updates only the `terrain_cells` dictionary on the map state. No rules, turn, or speed budget dependencies. Running it on the Tk main thread resolves off-thread Tk mutation risks.
* **Expected Focused Tests:**
  - `test_set_terrain_command_success` (execution, queue wait telemetry, trace validation)
  - `test_set_terrain_command_validation_failure` (error validation on coordinates)
  - `test_set_terrain_route_level_behavior_mapping` (route-to-facade mapping)

### 2. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Handler / Path:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4667) calling `self.app._dm_move_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **New Action Type Required:** No.
* **Payload Shape:**
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
* **Gameplay/State Risks:** **High**. Highly coupled with speed budgets, pathfinding, hazard/trap triggers, reaction logic, and turn state. Too risky to migrate at this phase.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST .../terrain/cell` (Toggle Terrain)** | No | Yes | **Low** | Updates only the terrain state dictionary. No complex rules or dependencies. Running it on the Tk main thread resolves off-thread Tk mutation risks. |
| **`POST .../move` (Rules Move)** | Yes | No | **High** | Rules-heavy, hazards, reactions, mounts, speed budget calculations. |

We recommend migrating **`POST /api/dm/map/terrain/cell` (Toggle Map Terrain Cell)** next.

By migrating the terrain cell command, we secure another FastAPI request handler onto the thread-safe Tk main thread queue adapter with minimal risk.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-terrain-cell`

### Exact route/command to migrate
- Route: `POST /api/dm/map/terrain/cell`
- Command: `COMMAND_SET_TERRAIN = "set_terrain"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch)
- `dnd_initative_tracker.py` (Update `dm_set_terrain_cell` route to delegate via facade, handle callback mapping to store `terrain_result` under `_action_states`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_SET_TERRAIN` success, validation failures, and route mappings)

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

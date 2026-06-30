# WORK-20260630-runtime-facade-next-queue-command-selection-12

## Status

Completed

## Title

Runtime facade next queue command selection 12

## Goal

Select the next safe, low-risk production command to route through the `ServerRuntimeFacade` queue adapter after spell color, combatant facing, aura overlays, place/reposition, AoE removal, AoE move, obstacle cell toggle, terrain cell toggle, elevation cell toggle, map settings, map backgrounds upsert, map background removal, map background ordering, map hazard upsert, and map hazard removal. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260630-runtime-facade-queue-command-hazard-remove](../completed/WORK-20260630-runtime-facade-queue-command-hazard-remove.md)
- [WORK-20260630-runtime-facade-queue-command-hazard-upsert](../completed/WORK-20260630-runtime-facade-queue-command-hazard-upsert.md)
- [WORK-20260630-runtime-facade-next-queue-command-selection-11](../completed/WORK-20260630-runtime-facade-next-queue-command-selection-11.md)

---

## Evidence Report

We evaluated the remaining candidate routes from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/features` (Create/Update Map Feature) and `DELETE /api/dm/map/features/{feature_id}` (Remove Map Feature)
* **Route Location & Handler Shape:** 
  - `dm_upsert_feature` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5782-L5819) calling `self.app._dm_upsert_feature_on_map(...)`.
  - `dm_remove_feature` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5821-L5835) calling `self.app._dm_remove_feature_on_map(...)`.
* **Existing `_actions` Mapping:** No. Will need to define new action constants:
  - `COMMAND_UPSERT_MAP_FEATURE = "upsert_map_feature"`
  - `COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"`
* **Payload Complexity:** Low.
  - Upsert requires `col`, `row`, `feature_id` (optional), `kind` (optional), `tactical_preset_id` (optional), `count` (optional), `name` (optional), and custom payload dictionary.
  - Remove requires `feature_id` path parameter.
* **Expected Response Shape:**
  - Upsert:
    ```json
    {
      "ok": true,
      "feature_id": string,
      "feature": dict,
      "snapshot": dict
    }
    ```
  - Remove:
    ```json
    {
      "ok": true,
      "feature_id": string,
      "snapshot": dict
    }
    ```
* **State Mutation Complexity:** Low. Adds or removes a feature entry from the `state.features` dictionary inside the canonical `MapState` via `_upsert_map_feature` / `_remove_map_feature` on the Tk/main thread, and triggers map redraws / broadcasts.
* **Gameplay/State Risks:** **Low**. Modifies static grid-based map entities. Decoupled from movement budgets, pathfinding algorithms, turn state, mounts/riders, reaction/opportunity prompts, HP changes, resource spending, spells, or combat loops. Safe to process on the Tk thread via the queue.
* **Expected Focused Tests:**
  - `test_upsert_feature_success` (verifies feature addition/update, queue wait telemetry, and trace logging)
  - `test_upsert_feature_validation_failure` (verifies out-of-bounds coordinates, invalid counts)
  - `test_remove_feature_success` (verifies feature removal)
  - `test_remove_feature_validation_failure` (verifies missing/non-existent feature_id)
  - `test_feature_routes_behavior_mapping` (verifies FastAPI route delegation)

### 2. `POST /api/dm/map/aoes` (Create Map AoE)
* **Route Location & Handler Shape:** `dm_create_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6464-L6473) calling `self.app._dm_create_aoe_on_map(payload)`.
* **Existing `_actions` Mapping:** No.
* **Payload Complexity:** Medium. Requires shape type, grid points (`cx`, `cy` or `col`, `row`), and dimension metrics (radius, width, length, etc.).
* **State Mutation Complexity:** Medium/High. Calls `_handle_cast_aoe_request` which resolves spell presets, checks counterspell reactions, updates resource spell slots, manages summon auto-spawns, and inserts the new AoE object.
* **Gameplay/State Risks:** **High**. Triggers deep spell preset and reaction/counterspell pipelines. Concurrency and timeout risks exist if a reaction prompt blocks the Tk thread queue, causing the HTTP route thread to time out. Unsuitable for migration at this phase.

### 3. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Location & Handler Shape:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4667-L4694) calling `self.app._dm_move_combatant_on_map(...)`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **Payload Complexity:** Low (`col` and `row` in the request body).
* **State Mutation Complexity:** High. Checks layout limits, pathfinding algorithms (`_lan_shortest_cost`), movement limits, mount/rider coordinate tracking, and triggers hazard traps or reaction prompts.
* **Gameplay/State Risks:** **High**. Coupled with pathfinding, mounts, traps, turn order, and blocking UI reaction prompts (e.g. opportunity attacks) that can pause the main thread queue indefinitely, risking HTTP timeouts. Highly unsafe.

### 4. `POST /api/dm/map/structures` (Create/Update Structure), `POST /api/dm/map/structures/{structure_id}/move` (Move Structure), and `DELETE /api/dm/map/structures/{structure_id}` (Remove Structure)
* **Route Location & Handler Shape:** 
  - `dm_upsert_structure` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5838-L5876) calling `self.app._dm_upsert_structure_on_map(...)`
  - `dm_move_structure` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5878-L5910) calling `self.app._dm_move_structure_on_map(...)`
  - `dm_remove_structure` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5912-L5926) calling `self.app._dm_remove_structure_on_map(...)`
* **Existing `_actions` Mapping:** No.
* **Payload/Mutation Complexity:** Medium/High. Requires structure dimensions (`width_cells`, `height_cells`), anchor coordinates, and list of `occupied_offsets`. Moving or placement checks against collision blocks and returns lists of blocking elements on failure.
* **Gameplay/State Risks:** **Medium**. Modifies static structures, but involves more complex multi-cell occupancy calculations and path blocker checks, making them slightly higher risk than simple single-cell features.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST /api/dm/map/features` & `DELETE /api/dm/map/features/{feature_id}`** | No | Yes | **Low** | Modifies map feature definitions on MapState. Runs on Tk thread. No gameplay side-effects or prompt loops. |
| **`POST /api/dm/map/aoes`** | No | Yes | **Medium/High** | Invokes deep spell preset, resource, and reaction/counterspell pipeline. |
| **`POST /api/dm/map/combatants/{cid}/move`** | Yes | No | **High** | Coupled with pathfinding, mounts, traps, turn order, and blocking UI prompts. |
| **`POST /api/dm/map/structures` & `DELETE /api/dm/map/structures/{sid}`** | No | Yes | **Medium** | Involves multi-cell structures, occupancy offsets, and collision/blocker tracking. |

We recommend migrating the feature-related endpoints next:
- **`POST /api/dm/map/features` (Create/Update Map Feature)**
- **`DELETE /api/dm/map/features/{feature_id}` (Remove Map Feature)**

These commands are very low risk as they strictly deal with grid-based tactical feature metadata, matching the safety profile of recent terrain/elevation/obstacle cell and hazard mutations. Migrating them completes the static map entity administration suite.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-features`

### Exact routes/commands to migrate
- Route: `POST /api/dm/map/features`
  - Command: `COMMAND_UPSERT_MAP_FEATURE = "upsert_map_feature"`
- Route: `DELETE /api/dm/map/features/{feature_id}`
  - Command: `COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constants and add dispatch branches in `submit_command`)
- `dnd_initative_tracker.py` (Update `dm_upsert_feature` and `dm_remove_feature` routes to delegate via facade, handle callback mapping to store results in `_action_states`, and process `upsert_map_feature` and `remove_map_feature` types in `_lan_apply_action`)
- `tests/test_server_runtime.py` (Focused tests for both commands: success, validation failures, and route mappings)

### Files explicitly out of scope
- `player_command_contracts.py`
- `player_command_service.py`
- `dnd_initative_tracker.py` combatant movement, reaction, or spellcasting logic.

### Focused validation commands for that future slice
```bash
python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
.venv/bin/python -m unittest tests/test_server_runtime.py
git status --short
timeout 10s git diff --check
```

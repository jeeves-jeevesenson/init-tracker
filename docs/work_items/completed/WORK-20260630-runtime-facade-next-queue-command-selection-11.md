# WORK-20260630-runtime-facade-next-queue-command-selection-11

## Status

Completed

## Title

Runtime facade next queue command selection 11

## Goal

Select the next safe, low-risk production command to route through the `ServerRuntimeFacade` queue adapter after spell color, combatant facing, aura overlays, place/reposition, AoE removal, AoE move, obstacle cell toggle, terrain cell toggle, elevation cell toggle, map settings, map backgrounds upsert, map background removal, and map background ordering. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260630-runtime-facade-queue-command-background-order](../completed/WORK-20260630-runtime-facade-queue-command-background-order.md)
- [WORK-20260630-runtime-facade-queue-command-background-remove](../completed/WORK-20260630-runtime-facade-queue-command-background-remove.md)
- [WORK-20260630-runtime-facade-next-queue-command-selection-10](../completed/WORK-20260630-runtime-facade-next-queue-command-selection-10.md)

---

## Evidence Report

We evaluated the remaining candidate routes from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/hazards` (Create/Update Map Hazard) and `DELETE /api/dm/map/hazards/{hazard_id}` (Remove Map Hazard)
* **Route Location & Handler Shape:** 
  - `dm_upsert_hazard` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5691-L5727) calling `self.app._dm_upsert_hazard_on_map(...)`.
  - `dm_remove_hazard` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5729-L5743) calling `self.app._dm_remove_hazard_on_map(...)`.
* **Existing `_actions` Mapping:** No. Will need to define new action constants:
  - `COMMAND_UPSERT_MAP_HAZARD = "upsert_map_hazard"`
  - `COMMAND_REMOVE_MAP_HAZARD = "remove_map_hazard"`
* **Payload Complexity:** Low.
  - Upsert requires `col`, `row`, `hazard_id` (optional), `kind` (optional), `tactical_preset_id` (optional), `count` (optional), `name` (optional), and custom payload dictionary.
  - Remove requires `hazard_id` path parameter.
* **Expected Response Shape:**
  - Upsert:
    ```json
    {
      "ok": true,
      "hazard_id": string,
      "hazard": dict,
      "snapshot": dict
    }
    ```
  - Remove:
    ```json
    {
      "ok": true,
      "hazard_id": string,
      "snapshot": dict
    }
    ```
* **State Mutation Complexity:** Low. Adds or removes a hazard entry from the `state.hazards` dictionary inside the canonical `MapState` via `_upsert_map_hazard` / `_remove_map_hazard` on the Tk/main thread, and triggers map redraws / broadcasts.
* **Gameplay/State Risks:** **Low**. Modifies static grid-based map entities. Decoupled from movement budgets, pathfinding algorithms, turn state, mounts/riders, reaction/opportunity prompts, HP changes, resource spending, spells, or combat loops. Safe to process on the Tk thread via the queue.
* **Expected Focused Tests:**
  - `test_upsert_hazard_success` (verifies hazard addition/update, queue wait telemetry, and trace logging)
  - `test_upsert_hazard_validation_failure` (verifies out-of-bounds coordinates, invalid counts)
  - `test_remove_hazard_success` (verifies hazard removal)
  - `test_remove_hazard_validation_failure` (verifies missing/non-existent hazard_id)
  - `test_hazard_routes_behavior_mapping` (verifies FastAPI route delegation)

### 2. `POST /api/dm/map/features` (Create/Update Map Feature) and `DELETE /api/dm/map/features/{feature_id}` (Remove Map Feature)
* **Route Location & Handler Shape:**
  - `dm_upsert_feature` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5745-L5782) calling `self.app._dm_upsert_feature_on_map(...)`.
  - `dm_remove_feature` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5784-L5798) calling `self.app._dm_remove_feature_on_map(...)`.
* **Existing `_actions` Mapping:** No. Will need to define new action constants:
  - `COMMAND_UPSERT_MAP_FEATURE = "upsert_map_feature"`
  - `COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"`
* **Payload Complexity:** Low. Similar to hazards.
* **Expected Response Shape:** Similar to hazards.
* **State Mutation Complexity:** Low. Adds or removes a feature entry from the `state.features` dictionary inside `MapState` via `_upsert_map_feature` / `_remove_map_feature`.
* **Gameplay/State Risks:** **Low**. Modifies static map features. Decoupled from movement budgets, pathfinding, turn state, mounts/riders, reaction/opportunity prompts, HP changes, resource spending, spells, or combat loops. Safe to process on the Tk thread via the queue.
* **Expected Focused Tests:** Similar structure to hazards.

### 3. `POST /api/dm/map/aoes` (Create Map AoE)
* **Route Location & Handler Shape:** `dm_create_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6427-L6446) calling `self.app._dm_create_aoe_on_map(payload)`.
* **Existing `_actions` Mapping:** No.
* **Payload Complexity:** Medium. Requires shape type, grid points (`cx`, `cy` or `col`, `row`), and dimension metrics (radius, width, length, etc.).
* **State Mutation Complexity:** Medium/High. Calls `_handle_cast_aoe_request` which resolves spell presets, checks counterspell reactions, updates resource spell slots, manages summon auto-spawns, and inserts the new AoE object.
* **Gameplay/State Risks:** **High**. Triggers deep spell preset and reaction/counterspell pipelines. Concurrency and timeout risks exist if a reaction prompt blocks the Tk thread queue, causing the HTTP route thread to time out. Unsuitable for migration at this phase.

### 4. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Location & Handler Shape:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4666-L4694) calling `self.app._dm_move_combatant_on_map(...)`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **Payload Complexity:** Low (`col` and `row` in the request body).
* **State Mutation Complexity:** High. Checks layout limits, pathfinding algorithms (`_lan_shortest_cost`), movement limits, mount/rider coordinate tracking, and triggers hazard traps or reaction prompts.
* **Gameplay/State Risks:** **High**. Coupled with pathfinding, mounts, traps, turn order, and blocking UI reaction prompts (e.g. opportunity attacks) that can pause the main thread queue indefinitely, risking HTTP timeouts. Highly unsafe.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST /api/dm/map/hazards` & `DELETE /api/dm/map/hazards/{hazard_id}`** | No | Yes | **Low** | Modifies map hazard definitions on MapState. Runs on Tk thread. No gameplay side-effects or prompt loops. |
| **`POST /api/dm/map/features` & `DELETE /api/dm/map/features/{feature_id}`** | No | Yes | **Low** | Modifies map feature definitions on MapState. Runs on Tk thread. No gameplay side-effects or prompt loops. |
| **`POST /api/dm/map/aoes`** | No | Yes | **Medium/High** | Invokes deep spell preset, resource, and reaction/counterspell pipeline. |
| **`POST /api/dm/map/combatants/{cid}/move`** | Yes | No | **High** | Coupled with pathfinding, mounts, traps, turn order, and blocking UI prompts. |

We recommend migrating the hazard-related endpoints next:
- **`POST /api/dm/map/hazards` (Create/Update Map Hazard)**
- **`DELETE /api/dm/map/hazards/{hazard_id}` (Remove Map Hazard)**

These commands are very low risk as they strictly deal with grid-based tactical hazard metadata, matching the safety profile of recent terrain/elevation/obstacle cell mutations. Migrating them completes a major portion of static map entity administration.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-hazards`

### Exact routes/commands to migrate
- Route: `POST /api/dm/map/hazards`
  - Command: `COMMAND_UPSERT_MAP_HAZARD = "upsert_map_hazard"`
- Route: `DELETE /api/dm/map/hazards/{hazard_id}`
  - Command: `COMMAND_REMOVE_MAP_HAZARD = "remove_map_hazard"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constants and add dispatch branches in `submit_command`)
- `dnd_initative_tracker.py` (Update `dm_upsert_hazard` and `dm_remove_hazard` routes to delegate via facade, handle callback mapping to store results in `_action_states`, and process `upsert_map_hazard` and `remove_map_hazard` types in `_lan_apply_action`)
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

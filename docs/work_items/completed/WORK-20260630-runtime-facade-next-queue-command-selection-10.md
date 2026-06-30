# WORK-20260630-runtime-facade-next-queue-command-selection-10

## Status

Completed

## Title

Runtime facade next queue command selection 10

## Goal

Select the next low-risk production command to route through the `ServerRuntimeFacade` queue adapter after facing, aura overlays, place/reposition, AoE removal, AoE move, obstacle cell toggle, terrain cell toggle, elevation cell toggle, map settings, and map backgrounds. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260630-runtime-facade-queue-command-backgrounds](../completed/WORK-20260630-runtime-facade-queue-command-backgrounds.md)
- [WORK-20260630-runtime-facade-next-queue-command-selection-9](../completed/WORK-20260630-runtime-facade-next-queue-command-selection-9.md)

---

## Evidence Report

We evaluated candidate routes from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `DELETE /api/dm/map/backgrounds/{bid}` (Remove Map Background Layer)
* **Route Location & Handler Shape:** `dm_remove_background` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6348-L6361) calling `self.app._dm_remove_background_layer(bid)`.
* **Existing `_actions` Mapping:** No. Will need to define a new action constant `COMMAND_REMOVE_MAP_BACKGROUND = "remove_map_background"`.
* **Payload Complexity:** Low. Only the integer ID `bid` passed as a path parameter.
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "bid": int,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Low. Removes the matching background entry from the `presentation["bg_images"]` list inside `MapState` via `_mutate_canonical_map_state` on the Tk/main thread, adjusts `next_bg_id` as needed, and restores the backgrounds via `_restore_map_backgrounds(...)`.
* **Gameplay/State Risks:** **Low**. Purely visual presentation layer metadata. Decoupled from rules, movement budgets, pathfinding, turn state, hazards, mounts/riders, prompts, opportunity/reaction behavior, HP, spells, combat state, AoE lifecycle, or queue timeout behavior. Run safely on the Tk thread.
* **Expected Focused Tests:**
  - `test_remove_background_success` (verifies background removal, queue wait telemetry, trace validation)
  - `test_remove_background_validation_failure` (verifies non-existent or invalid bid handling)
  - `test_remove_background_route_level_behavior_mapping` (verifies route delegation)

### 2. `POST /api/dm/map/backgrounds/{bid}/order` (Reorder Map Background Layer)
* **Route Location & Handler Shape:** `dm_reorder_background` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6363-L6384) calling `self.app._dm_reorder_background_layer(bid=bid, direction=direction)`.
* **Existing `_actions` Mapping:** No. Will need to define a new action constant `COMMAND_REORDER_MAP_BACKGROUND = "reorder_map_background"`.
* **Payload Complexity:** Low. Requires a body payload with direction (`"up"`, `"down"`, `"front"`, or `"back"`) and the path parameter `bid`.
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "bid": int,
    "background": dict,
    "backgrounds": list,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Low. Finds the target layer index in `presentation["bg_images"]`, rearranges it within the list based on the direction command, normalizes the stack IDs, calls `_mutate_canonical_map_state` on the Tk/main thread, restores the layers via `_restore_map_backgrounds(...)`, and returns the updated background entries with computed asset URLs.
* **Gameplay/State Risks:** **Low**. Purely visual presentation layer metadata. Decoupled from rules, movement budgets, pathfinding, turn state, hazards, mounts/riders, prompts, opportunity/reaction behavior, HP, spells, combat state, AoE lifecycle, or queue timeout behavior. Run safely on the Tk thread.
* **Expected Focused Tests:**
  - `test_reorder_background_success` (verifies reordering with up/down/front/back directions, queue wait telemetry, trace validation)
  - `test_reorder_background_validation_failure` (verifies invalid bid or invalid direction handling)
  - `test_reorder_background_route_level_behavior_mapping` (verifies route delegation)

### 3. `POST /api/dm/map/aoes` (Create Map AoE)
* **Route Location & Handler Shape:** `dm_create_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6386-L6407) calling `self.app._dm_create_aoe_on_map(payload)`.
* **Existing `_actions` Mapping:** No.
* **Payload Complexity:** Medium. Requires shape type, grid points (`cx`, `cy` or `col`, `row`), and dimension metrics (radius, width, length, etc.).
* **State Mutation Complexity:** Medium/High. Invokes `_handle_cast_aoe_request` which resolves spell presets, checks counterspell/reaction triggers, updates resource spell slots, manages summon auto-spawns, and inserts the new AoE object.
* **Gameplay/State Risks:** **High**. Triggers the deep spell preset and reaction/counterspell prompt pipelines. Concurrency and timeout risks exist if a reaction prompt blocks the Tk thread queue, causing the HTTP route thread to time out. Unsuitable for migration at this phase.

### 4. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Location & Handler Shape:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4666-L4694) calling `self.app._dm_move_combatant_on_map(...)`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **Payload Complexity:** Low (`col` and `row` in the request body).
* **State Mutation Complexity:** High. Checks layout limits, pathfinding algorithms (`_lan_shortest_cost`), movement limits, mount/rider tracking, and triggers hazard traps or reaction prompts.
* **Gameplay/State Risks:** **High**. Direct integration with pathfinding, opportunity attacks, hazard traps, and reaction prompts that can block the Tk thread queue indefinitely, leading to HTTP client timeouts. Highly unsafe.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`DELETE /api/dm/map/backgrounds/{bid}`** | No | Yes | **Low** | Modifies background image list on MapState. Runs on Tk thread. No gameplay side-effects. |
| **`POST /api/dm/map/backgrounds/{bid}/order`** | No | Yes | **Low** | Modifies background layer order on MapState. Runs on Tk thread. No gameplay side-effects. |
| **`POST /api/dm/map/aoes`** | No | Yes | **Medium/High** | Invokes deep spell preset, resource, and reaction/counterspell pipeline. |
| **`POST /api/dm/map/combatants/{cid}/move`** | Yes | No | **High** | Coupled with pathfinding, mounts, traps, turn order, and blocking UI prompts. |

We recommend migrating the remaining two background-related endpoints next:
- **`DELETE /api/dm/map/backgrounds/{bid}` (Remove Map Background Layer)**
- **`POST /api/dm/map/backgrounds/{bid}/order` (Reorder Map Background Layer)**

These commands are very low risk as they strictly deal with visual presentation layers, matching the safety profile of `POST /api/dm/map/backgrounds`. Recommending migrating them together completes the map backgrounds management functionality.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-background-manipulation`

### Exact routes/commands to migrate
- Route: `DELETE /api/dm/map/backgrounds/{bid}`
  - Command: `COMMAND_REMOVE_MAP_BACKGROUND = "remove_map_background"`
- Route: `POST /api/dm/map/backgrounds/{bid}/order`
  - Command: `COMMAND_REORDER_MAP_BACKGROUND = "reorder_map_background"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constants and add dispatch branches in `submit_command`)
- `dnd_initative_tracker.py` (Update `dm_remove_background` and `dm_reorder_background` routes to delegate via facade, handle callback mapping to store results in `_action_states`, and process `remove_map_background` and `reorder_map_background` types in `_lan_apply_action`)
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

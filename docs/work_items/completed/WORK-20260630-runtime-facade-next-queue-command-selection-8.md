# WORK-20260630-runtime-facade-next-queue-command-selection-8

## Status

Completed

## Title

Runtime facade next queue command selection 8

## Goal

Select the next low-risk production command to route through the `ServerRuntimeFacade` queue adapter after facing, aura overlays, place/reposition, AoE removal, AoE move, obstacle cell toggle, terrain cell toggle, and elevation cell toggle. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260630-runtime-facade-queue-command-elevation-cell](../completed/WORK-20260630-runtime-facade-queue-command-elevation-cell.md)
- [WORK-20260630-runtime-facade-next-queue-command-selection-7](../completed/WORK-20260630-runtime-facade-next-queue-command-selection-7.md)

---

## Evidence Report

We evaluated candidate routes from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/settings` (Set Map Grid Settings)
* **Route Location & Handler Shape:** `dm_set_map_settings` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5536-L5557) calling `self.app._dm_set_map_grid_settings(cols=body.get("cols"), rows=body.get("rows"))`.
* **Existing `_actions` Mapping:** No. Will need to define a new action constant `COMMAND_SET_MAP_SETTINGS = "set_map_settings"`.
* **Payload Complexity:** Low. Takes simple columns and rows integers:
  ```json
  {
    "cols": int,
    "rows": int
  }
  ```
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "grid": {
      "cols": int,
      "rows": int,
      "feet_per_square": float
    },
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Low. Mutates the `grid` property on `MapState` inside `_mutate_canonical_map_state(..., hydrate_window=True, broadcast=True)` to update grid columns, rows, and default scaling.
* **Gameplay/State Risks:** **Low**. Updates only grid boundaries. Does not affect turn order, combat status, HP, status conditions, mounts/riders logic, or reaction prompts. Shrinking grid dimensions when active combatants or active AoEs are outside boundaries is a potential validation edge-case but behaves as standard DM-driven resizing. Safe to execute asynchronously on the Tk thread via the queue.
* **Expected Focused Tests:**
  - `test_set_map_settings_success` (verifies grid resize, queue wait telemetry, trace validation)
  - `test_set_map_settings_validation_failure` (verifies out-of-bounds or non-integer errors)
  - `test_set_map_settings_route_level_behavior_mapping` (verifies route delegation)

### 2. `POST /api/dm/map/backgrounds` (Upsert Map Background Layer)
* **Route Location & Handler Shape:** `dm_upsert_background` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6277-L6312) calling `self.app._dm_upsert_background_layer(...)`.
* **Existing `_actions` Mapping:** No. Will need to define a new action constant `COMMAND_UPSERT_BACKGROUND = "upsert_background"`.
* **Payload Complexity:** Low to Medium.
  ```json
  {
    "asset_path": string,
    "bid": int,
    "x": float,
    "y": float,
    "scale_pct": float,
    "trans_pct": float,
    "locked": bool
  }
  ```
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "background": dict,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Low to Medium. Performs asset path validation, checks scale/opacity limits, then mutates the `presentation["bg_images"]` list within `MapState` via `_mutate_canonical_map_state`. It also calls helper methods to restore backgrounds or generate asset URLs.
* **Gameplay/State Risks:** **Low**. Purely presentation-oriented. Bypasses all combatant, movement, hazard, spell, and reaction rules.
* **Expected Focused Tests:**
  - `test_upsert_background_success`
  - `test_upsert_background_validation_failure`
  - `test_upsert_background_route_level_behavior_mapping`

### 3. `POST /api/dm/map/aoes` (Create Map AoE)
* **Route Location & Handler Shape:** `dm_create_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6352-L6372) calling `self.app._dm_create_aoe_on_map(payload)`.
* **Existing `_actions` Mapping:** No.
* **Payload Complexity:** Medium. Requires shape type, grid points (`cx`, `cy` or `col`, `row`), and dimension metrics (radius, width, length, etc.).
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "aid": int,
    "aoe": dict,
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Medium/High. Direct call to `_handle_cast_aoe_request` resolves spell presets, checks counterspell reactions, updates resource spell slots, manages summon auto-spawns, and inserts the new AoE object into active map states.
* **Gameplay/State Risks:** **Medium/High**. Even though the DM-facing route `/api/dm/map/aoes` bypasses player turn limits and resource spending checks because `is_admin=True` and `cid=None`, it triggers the entire spellcasting/AoE-handling pipeline. This includes checks for reactions (like Counterspell), summons, and tactical state updates which present significant concurrency risks and pathfinding coupling compared to simple grid or background mutations.
* **Expected Focused Tests:**
  - `test_create_aoe_command_success`
  - `test_create_aoe_command_validation_failure`
  - `test_create_aoe_route_level_behavior_mapping`

### 4. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Location & Handler Shape:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4666-L4694) calling `self.app._dm_move_combatant_on_map(...)`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **Payload Complexity:** Low (`col` and `row` in the request body).
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
* **State Mutation Complexity:** High. Checks layout limits, pathfinding algorithms (`_lan_shortest_cost`), movement limits, mount/rider coordinate tracking, and triggers hazard traps or reaction prompts.
* **Gameplay/State Risks:** **High**. Deeply integrated with player budgets, status overrides, and reaction dialogues. Reaction popups can block the queue main thread indefinitely, risking HTTP queue timeouts. Highly unsafe for the current phase.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST .../settings` (Grid settings)** | No | Yes | **Low** | Modifies grid width/height on MapState. Runs on Tk thread. No gameplay side-effects. |
| **`POST .../backgrounds` (Upsert background)** | No | Yes | **Low** | Purely visual presentation layer metadata. No gameplay side-effects. Slightly higher code complexity than settings. |
| **`POST .../aoes` (Create AoE)** | No | Yes | **Medium/High** | Invokes deep spell preset and reaction/counterspell pipeline. |
| **`POST .../move` (Rules Move)** | Yes | No | **High** | Coupled with pathfinding, mounts, traps, turn order, and blocking UI prompts. |

We recommend migrating **`POST /api/dm/map/settings` (Set Map Grid Settings)** next. 

This command is the lowest-risk candidate. It deals strictly with grid dimension modifications on the MapState via a thread-safe mutation inside `_mutate_canonical_map_state` on the Tk main thread, ensuring zero risk to movement budgets, hazards, reaction alerts, or gameplay mechanics.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-map-settings`

### Exact route/command to migrate
- Route: `POST /api/dm/map/settings`
- Command: `COMMAND_SET_MAP_SETTINGS = "set_map_settings"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch in `submit_command`)
- `dnd_initative_tracker.py` (Update `dm_set_map_settings` route to delegate via facade, handle callback mapping to store `settings_result` under `_action_states`, and process `set_map_settings` type in `_lan_apply_action`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_SET_MAP_SETTINGS` success, validation failures, and route mappings)

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

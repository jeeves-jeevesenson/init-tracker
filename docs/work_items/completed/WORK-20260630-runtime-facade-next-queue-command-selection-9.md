# WORK-20260630-runtime-facade-next-queue-command-selection-9

## Status

Completed

## Title

Runtime facade next queue command selection 9

## Goal

Select the next low-risk production command to route through the `ServerRuntimeFacade` queue adapter after facing, aura overlays, place/reposition, AoE removal, AoE move, obstacle cell toggle, terrain cell toggle, elevation cell toggle, and map settings. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260630-runtime-facade-queue-command-map-settings](../completed/WORK-20260630-runtime-facade-queue-command-map-settings.md)
- [WORK-20260630-runtime-facade-next-queue-command-selection-8](../completed/WORK-20260630-runtime-facade-next-queue-command-selection-8.md)

---

## Evidence Report

We evaluated candidate routes from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/backgrounds` (Upsert Map Background Layer)
* **Route Location & Handler Shape:** `dm_upsert_background` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6294-L6328) calling `self.app._dm_upsert_background_layer(...)`.
* **Existing `_actions` Mapping:** No. Will need to define a new action constant `COMMAND_UPSERT_BACKGROUND = "upsert_background"`.
* **Payload Complexity:** Low to Medium.
  ```json
  {
    "asset_path": string,
    "bid": int (optional),
    "x": float (optional),
    "y": float (optional),
    "scale_pct": float (optional),
    "trans_pct": float (optional),
    "locked": bool (optional)
  }
  ```
* **Expected Response Shape:**
  ```json
  {
    "ok": true,
    "background": {
      "bid": int,
      "path": string,
      "x": float,
      "y": float,
      "scale_pct": float,
      "trans_pct": float,
      "locked": bool,
      "asset_url": string
    },
    "snapshot": dict
  }
  ```
* **State Mutation Complexity:** Low to Medium. Performs asset path validation, checks scale/opacity limits, then mutates the `presentation["bg_images"]` list within `MapState` via `_mutate_canonical_map_state` on the Tk/main thread. It also restores backgrounds via `_restore_map_backgrounds(...)` and generates asset URLs.
* **Gameplay/State Risks:** **Low**. Purely visual presentation layer metadata. Decoupled from rules, movement budgets, pathfinding, turn state, hazards, mounts/riders, prompts, opportunity/reaction behavior, HP, spells, combat state, AoE lifecycle, or queue timeout behavior. Run safely on the Tk thread.
* **Expected Focused Tests:**
  - `test_upsert_background_success` (verifies background creation/update, queue wait telemetry, trace validation)
  - `test_upsert_background_validation_failure` (verifies negative scale, invalid bid, invalid/missing asset path)
  - `test_upsert_background_route_level_behavior_mapping` (verifies route delegation)

### 2. `POST /api/dm/map/aoes` (Create Map AoE)
* **Route Location & Handler Shape:** `dm_create_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6369-L6390) calling `self.app._dm_create_aoe_on_map(payload)`.
* **Existing `_actions` Mapping:** No. Will need to define a new action constant `COMMAND_CREATE_AOE = "create_aoe"`.
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
* **State Mutation Complexity:** Medium/High. Calls `_handle_cast_aoe_request` which resolves spell presets, checks counterspell reactions, updates resource spell slots, manages summon auto-spawns, and inserts the new AoE object into active map states.
* **Gameplay/State Risks:** **Medium/High**. Invokes deep spell preset and reaction/counterspell pipelines. This presents concurrency and timeout risks if a reaction prompt blocks the Tk thread queue, making it unsuitable for a low-risk migration phase.

### 3. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
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
* **Gameplay/State Risks:** **High**. Coupled with pathfinding, mounts, traps, turn order, and blocking UI reaction prompts (e.g. opportunity attacks) that can pause the main thread queue indefinitely, risking HTTP timeouts. Highly unsafe.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST /api/dm/map/backgrounds`** | No | Yes | **Low** | Modifies background image list on MapState. Runs on Tk thread. No gameplay side-effects. |
| **`POST /api/dm/map/aoes`** | No | Yes | **Medium/High** | Invokes deep spell preset, resource, and reaction/counterspell pipeline. |
| **`POST /api/dm/map/combatants/{cid}/move`** | Yes | No | **High** | Coupled with pathfinding, mounts, traps, turn order, and blocking UI prompts. |

We recommend migrating **`POST /api/dm/map/backgrounds` (Upsert Map Background Layer)** next.

This command is the lowest-risk candidate. It deals strictly with visual background layers and is decoupled from all combatant movement, pathfinding, hazard, turn, or combat rules.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260630-runtime-facade-queue-command-backgrounds`

### Exact route/command to migrate
- Route: `POST /api/dm/map/backgrounds`
- Command: `COMMAND_UPSERT_BACKGROUND = "upsert_background"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch in `submit_command`)
- `dnd_initative_tracker.py` (Update `dm_upsert_background` route to delegate via facade, handle callback mapping to store `background_result` under `_action_states`, and process `upsert_background` type in `_lan_apply_action`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_UPSERT_BACKGROUND` success, validation failures, and route mappings)

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

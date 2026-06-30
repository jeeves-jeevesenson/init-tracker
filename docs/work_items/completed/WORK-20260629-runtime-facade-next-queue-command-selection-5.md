# WORK-20260629-runtime-facade-next-queue-command-selection-5

## Status

Completed

## Title

Runtime facade next queue command selection 5

## Goal

Select the next low-risk production command to route through the ServerRuntimeFacade queue adapter after facing, aura overlays, place/reposition, AoE removal, and AoE move. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260629-runtime-facade-queue-command-aoe-move](../completed/WORK-20260629-runtime-facade-queue-command-aoe-move.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-4](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-4.md)
- [WORK-20260629-runtime-facade-queue-command-aoe-remove](../completed/WORK-20260629-runtime-facade-queue-command-aoe-remove.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-3](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-3.md)
- [WORK-20260629-runtime-facade-queue-command-place](../completed/WORK-20260629-runtime-facade-place.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-2](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-2.md)
- [WORK-20260629-runtime-facade-queue-command-auras](../completed/WORK-20260629-runtime-facade-queue-command-auras.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection](../completed/WORK-20260629-runtime-facade-next-queue-command-selection.md)
- [WORK-20260629-runtime-facade-queue-command-facing](../completed/WORK-20260629-runtime-facade-queue-command-facing.md)
- [WORK-20260629-runtime-facade-queue-adapter](../completed/WORK-20260629-runtime-facade-queue-adapter.md)

---

## Evidence Report

We evaluated the following candidates from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/obstacles/cell` (Toggle Map Obstacle Cell)
* **Route Handler / Path:** `dm_set_obstacle_cell` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5558-L5591) calling `self.app._dm_set_obstacle_on_map(int(col), int(row), bool(blocked))`.
* **Existing `_actions` Mapping:** No. Will need to define a new action/message type `set_obstacle`.
* **New Action Type Required:** Yes.
* **Payload Shape:** `{"col": int, "row": int, "blocked": bool}`.
* **Expected Response Shape:** `{"ok": True, "col": int, "row": int, "blocked": bool, "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low**. Updates only the obstacles dictionary on the map state. No rules, turn, or speed budget dependencies. Safely redirects Tk state mutations (`_mutate_canonical_map_state`) to the Tk thread instead of the concurrent request thread.
* **Focused Validation:** Add mocks for checking/setting obstacles, success case (execution, trace validation), and route-level behavior validation.

### 2. `POST /api/dm/map/terrain/cell` (Toggle Map Terrain Cell)
* **Route Handler / Path:** `dm_set_terrain_cell` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L5593-L5637) calling `self.app._dm_set_terrain_on_map(int(col), int(row), is_rough=..., movement_type=..., color=..., label=...)`.
* **Existing `_actions` Mapping:** No.
* **New Action Type Required:** Yes.
* **Payload Shape:** `{"col": int, "row": int, "is_rough": bool, "movement_type": str, "color": Optional[str], "label": Optional[str]}`.
* **Expected Response Shape:** `{"ok": True, "col": int, "row": int, "is_rough": bool, "movement_type": str, "color": Optional[str], "label": Optional[str], "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low-Medium**. Modifies rough terrain settings. Slightly more complex payload and settings structure than cell obstacles, but still low risk.
* **Focused Validation:** Terrain mutation checks, response mapping verification.

### 3. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Handler / Path:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4667) calling `self.app._dm_move_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** Yes (`"move"`).
* **New Action Type Required:** No.
* **Payload Shape:** `{"col": int, "row": int}`.
* **Expected Response Shape:** `{"ok": True, "cid": int, "col": int, "row": int, "spent_ft": int, "snapshot": Dict}`.
* **Gameplay/State Risks:** **High**. Highly coupled with speed budgets, pathfinding, hazard/trap triggers, reaction logic, and turn state. Too risky to migrate at this phase.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST .../obstacles/cell` (Toggle Obstacle)** | No | Yes | **Low** | Simple cell passability toggle. No gameplay rules. Running it on the Tk main thread resolves off-thread Tk mutation risks. |
| **`POST .../terrain/cell` (Toggle Terrain)** | No | Yes | **Low-Medium** | Low risk, but has slightly more parameters than toggling cell obstacles. |
| **`POST .../move` (Rules Move)** | Yes | No | **High** | Rules-heavy, hazards, reactions, mounts, speed budget calculations. |

We recommend migrating **`POST /api/dm/map/obstacles/cell` (Toggle Map Obstacle Cell)** next.

By migrating the cell obstacle command, we secure another concurrent FastAPI request handler onto the thread-safe Tk main thread queue adapter with minimal risk.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260629-runtime-facade-queue-command-obstacle-cell`

### Exact route/command to migrate
- Route: `POST /api/dm/map/obstacles/cell`
- Command: `COMMAND_SET_OBSTACLE = "set_obstacle"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch)
- `dnd_initative_tracker.py` (Update `dm_set_obstacle_cell` route to delegate via facade, handle callback mapping to store `obstacle_result` under `_action_states`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_SET_OBSTACLE` success, validation failures, and route mappings)

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

---

## Completion Notes

Completed evidence/planning slice after evaluating cell obstacles, cell rough terrain, and rules-aware combatant move candidates.

Recommendation: migrate `POST /api/dm/map/obstacles/cell` next as `WORK-20260629-runtime-facade-queue-command-obstacle-cell`.

No app implementation was performed in this slice.

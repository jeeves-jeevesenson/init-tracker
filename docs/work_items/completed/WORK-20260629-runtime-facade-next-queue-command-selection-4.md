# WORK-20260629-runtime-facade-next-queue-command-selection-4

## Status

Completed

## Title

Runtime facade next queue command selection 4

## Goal

Select the next low-risk production command to route through the ServerRuntimeFacade queue adapter after facing, aura overlays, place/reposition, and AoE removal. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260629-runtime-facade-queue-command-aoe-remove](../completed/WORK-20260629-runtime-facade-queue-command-aoe-remove.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-3](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-3.md)
- [WORK-20260629-runtime-facade-queue-command-place](../completed/WORK-20260629-runtime-facade-queue-command-place.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-2](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-2.md)
- [WORK-20260629-runtime-facade-queue-command-auras](../completed/WORK-20260629-runtime-facade-queue-command-auras.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection](../completed/WORK-20260629-runtime-facade-next-queue-command-selection.md)
- [WORK-20260629-runtime-facade-queue-command-facing](../completed/WORK-20260629-runtime-facade-queue-command-facing.md)
- [WORK-20260629-runtime-facade-queue-adapter](../completed/WORK-20260629-runtime-facade-queue-adapter.md)

---

## Evidence Report

We evaluated the following candidates from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/aoes/{aid}/move` (Move Map AoE)
* **Route Handler / Path:** `dm_move_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6321-L6339) calling `self.app._dm_move_aoe_on_map(int(aid), payload)`.
* **Existing `_actions` Mapping:** Yes. `"aoe_move"` is defined in `LanController._ACTION_MESSAGE_TYPES` and routed via `PlayerCommandService.aoe_move`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"cx": float, "cy": float, "angle_deg": Optional[float], "ax": Optional[float], "ay": Optional[float], "spread_deg": Optional[float]}`.
* **Expected Response Shape:** `{"ok": True, "aid": int, "aoe": Dict, "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low-Medium**. Admin movement bypasses movement limit and turn enforcement checks, but need to check AoE presence in the global `_lan_aoes` store, handle rotatable geometry features, and correctly coordinate with owner facing synch.
* **Focused Validation:** Mocks for checking AoE presence and movement in the facade. Success execution case (command execution, trace validation), validation error mapping (missing/non-numeric cx/cy, AoE not found, etc.), and route-level behavior validation.

### 2. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Handler / Path:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4667) calling `self.app._dm_move_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** Yes. `"move"` is defined in `LanController._ACTION_MESSAGE_TYPES` and routed via `PlayerCommandService.move`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"col": int, "row": int}`.
* **Expected Response Shape:** `{"ok": True, "cid": int, "col": int, "row": int, "spent_ft": int, "snapshot": Dict}`.
* **Gameplay/State Risks:** **High**. Movement checks speed budgets (`_lan_shortest_cost`), conditions, turn enforcement, opportunity attacks, mounts/riders, and environmental hazard triggers. Highly coupled and risky to run asynchronously over the queue seam.
* **Focused Validation:** Pathfinding verification, speed cost deduction, mounting/rider sync, environmental/tether triggers, and route mapping tests.

### 3. Narrower production commands represented by PlayerCommandService/LanController action dictionaries.
* **Route Handler / Path:** N/A.
* **Existing `_actions` Mapping:** Various options exist (e.g. `cycle_movement_mode`, `dash`, `end_turn`), but they do not correspond to standalone map/overlay DM endpoints.
* **New Action Type Required:** N/A.
* **Payload Shape:** N/A.
* **Expected Response Shape:** N/A.
* **Gameplay/State Risks:** None of these are clearly lower risk than AoE move while also being map-related tactical API routes.
* **Focused Validation:** N/A.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST .../aoes/{aid}/move` (Move AoE)** | Yes | No | **Low-Medium** | Bypasses turn/movement limits for DMs. Updates coordinate/geometry data in `_lan_aoes`. Much simpler than combatant rules-move. |
| **`POST .../move` (Rules Move)** | Yes | No | **High** | Heavily coupled with gameplay rules, speed budgets, mounts/riders, tethers, hazards, and reaction triggers. |

We recommend migrating **`POST /api/dm/map/aoes/{aid}/move` (Move Map AoE)** next.

By migrating the AoE move command, we continue our map overlay extraction sequence safely. It aligns with the completed aura, place, and remove slices.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260629-runtime-facade-queue-command-aoe-move`

### Exact route/command to migrate
- Route: `POST /api/dm/map/aoes/{aid}/move`
- Command: `COMMAND_MOVE_AOE = "aoe_move"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch)
- `dnd_initative_tracker.py` (Update `dm_move_aoe` route to delegate via facade, handle callback mapping to store `move_result` under `_action_states`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_MOVE_AOE` success, validation failures, and route mappings)

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

Completed evidence/planning slice after evaluating AoE move, combatant move, and narrower player command candidates.

Recommendation: migrate `POST /api/dm/map/aoes/{aid}/move` next as `WORK-20260629-runtime-facade-queue-command-aoe-move`.

No app implementation was performed in this slice.

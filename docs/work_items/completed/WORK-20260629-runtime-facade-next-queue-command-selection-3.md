# WORK-20260629-runtime-facade-next-queue-command-selection-3

## Status

Completed

## Title

Runtime facade next queue command selection 3

## Goal

Select the next low-risk production command to route through the ServerRuntimeFacade queue adapter after facing, aura overlays, and place/reposition. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260629-runtime-facade-queue-command-place](../completed/WORK-20260629-runtime-facade-queue-command-place.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection-2](../completed/WORK-20260629-runtime-facade-next-queue-command-selection-2.md)
- [WORK-20260629-runtime-facade-queue-command-auras](../completed/WORK-20260629-runtime-facade-queue-command-auras.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection](../completed/WORK-20260629-runtime-facade-next-queue-command-selection.md)
- [WORK-20260629-runtime-facade-queue-command-facing](../completed/WORK-20260629-runtime-facade-queue-command-facing.md)
- [WORK-20260629-runtime-facade-queue-adapter](../completed/WORK-20260629-runtime-facade-queue-adapter.md)

---

## Evidence Report

We evaluated the following candidates from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `DELETE /api/dm/map/aoes/{aid}` (Remove Map AoE)
* **Route Handler / Path:** `dm_remove_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6340-L6355) calling `self.app._dm_remove_aoe_on_map(int(aid))`.
* **Existing `_actions` Mapping:** Yes. `"aoe_remove"` is defined in `LanController._ACTION_MESSAGE_TYPES` and routed via `PlayerCommandService.aoe_remove`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"aid": int}`.
* **Expected Response Shape:** `{"ok": True, "aid": int, "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low**. Simply deletes an active AoE overlay. Bypasses movement costs, turn permissions (when called by DM/admin), and coordinates. Easy validation.
* **Focused Validation:** Simple mock queue checks for `"aoe_remove"`.

### 2. `POST /api/dm/map/aoes/{aid}/move` (Move Map AoE)
* **Route Handler / Path:** `dm_move_aoe` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L6321-L6339) calling `self.app._dm_move_aoe_on_map(int(aid), payload)`.
* **Existing `_actions` Mapping:** Yes. `"aoe_move"` is defined in `LanController._ACTION_MESSAGE_TYPES` and routed via `PlayerCommandService.aoe_move`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"col": int, "row": int, "cx": float, "cy": float, "angle_deg": float, ...}`.
* **Expected Response Shape:** `{"ok": True, "aid": int, "aoe": Dict, "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low-Medium**. Modifies AoE parameters. While player-cast AoE movement checks action economy and range/speed limits, DM-facing admin movement bypasses these limitations. Still requires checking that the AoE exists and is not fixed to its caster.
* **Focused Validation:** Mocks for checking AoE presence and movement.

### 3. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Handler / Path:** `dm_move_combatant_on_map` in [dnd_initative_tracker.py](../../dnd_initative_tracker.py#L4665-L4693) calling `self.app._dm_move_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** Yes. `"move"` is defined in `LanController._ACTION_MESSAGE_TYPES` and routed via `PlayerCommandService.move`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"col": int, "row": int}`.
* **Expected Response Shape:** `{"ok": True, "cid": int, "col": int, "row": int, "spent_ft": int, "snapshot": Dict}`.
* **Gameplay/State Risks:** **High**. Standard movement checks speed budgets, conditions, active turn state (turn restrictions block non-admin movement), opportunity attacks, triggers client warnings (e.g. John's echo warning), tethers, and environment hazards. Highly coupled and risky to run asynchronously over the queue seam.
* **Focused Validation:** Highly complex testing setups for pathing, speed costs, and hazard triggers.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`DELETE .../aoes/{aid}` (Remove AoE)** | Yes | No | **Low** | Global overlay removal. Bypasses speed, geometry, and coordinates. Simple to delegate. |
| **`POST .../aoes/{aid}/move` (Move AoE)** | Yes | No | **Low-Medium** | Modifies coordinates/rotation of an active AoE shape. Relatively safe but more logic than removal. |
| **`POST .../move` (Rules Move)** | Yes | No | **High** | Heavily coupled with gameplay rules, speed budgets, reactions, hazards, and prompt triggers. |

We recommend migrating **`DELETE /api/dm/map/aoes/{aid}` (Remove Map AoE)** next.

By migrating the AoE removal command, we progress our extraction without hitting complex gameplay checks. The `"aoe_remove"` command is already registered under `LanController._ACTION_MESSAGE_TYPES` and maps cleanly to the legacy tracker dispatcher. Moving this route to the facade runtime queue seam allows us to safely isolate another active map mutation route with minimal code changes.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260629-runtime-facade-queue-command-aoe-remove`

### Exact route/command to migrate
- Route: `DELETE /api/dm/map/aoes/{aid}`
- Command: `COMMAND_REMOVE_AOE = "aoe_remove"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch)
- `dnd_initative_tracker.py` (Update `dm_remove_aoe` route to delegate via facade, handle `action_id` callback mapping to store `remove_result` under `_action_states`)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_REMOVE_AOE` success, traces, and route mappings)

### Files explicitly out of scope
- `player_command_contracts.py`
- `player_command_service.py`
- `dnd_initative_tracker.py` movement or spellcasting logic.

### Focused validation commands for that future slice
```bash
python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
.venv/bin/python -m unittest tests/test_server_runtime.py
git status --short
timeout 10s git diff --check
```


---

## Completion Notes

Completed evidence/planning slice after evaluating AoE remove, AoE move, and combatant move candidates.

Recommendation: migrate `DELETE /api/dm/map/aoes/{aid}` next as `WORK-20260629-runtime-facade-queue-command-aoe-remove`.

No app implementation was performed in this slice.

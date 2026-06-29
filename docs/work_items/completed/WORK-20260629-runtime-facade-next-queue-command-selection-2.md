# WORK-20260629-runtime-facade-next-queue-command-selection-2

## Status

Completed

## Title

Runtime facade next queue command selection 2

## Goal

Select the next low-risk production command to route through the ServerRuntimeFacade queue adapter after the completed facing and aura overlay migrations. Evidence/planning only; no app implementation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:
- [WORK-20260629-runtime-facade-queue-command-auras](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-auras.md)
- [WORK-20260629-runtime-facade-next-queue-command-selection](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-next-queue-command-selection.md)
- [WORK-20260629-runtime-facade-queue-command-facing](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-facing.md)
- [WORK-20260629-runtime-facade-queue-adapter](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md)

---

## Evidence Report

We evaluated the following candidates from the codebase for migration through the `ServerRuntimeFacade` queue adapter:

### 1. `POST /api/dm/map/combatants/{cid}/place` (Reposition Token)
* **Route Handler / Path:** `dm_place_combatant_on_map` in `dnd_initative_tracker.py` (lines 4696-4722) calling `self.app._dm_place_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** None. This command currently bypasses the queue and runs synchronously on the request thread.
* **New Action Type Required:** Yes. We will need to register `"place_combatant"` (or similar) in `LanController._ACTION_MESSAGE_TYPES` and map it inside `_lan_apply_action`.
* **Payload Shape:** `{"col": int, "row": int}` from client, with the addition of `cid` and `admin_token` during dispatch.
* **Expected Response Shape:** `{"ok": True, "cid": int, "col": int, "row": int, "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low-Medium**. While it bypasses movement costs and turn permissions, it performs coordinate bounds and occupancy checks, updates mount/rider structures, syncs caster-fixed AOEs, triggers environmental damage/effects via `_lan_handle_environment_triggers_for_moved_unit`, and validates John's echo tethers.
* **Focused Validation:** We can easily test enqueuing this action using the fake queue adapter and verify correct Tk-thread execution using mocks.

### 2. `POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)
* **Route Handler / Path:** `dm_move_combatant_on_map` in `dnd_initative_tracker.py` (lines 4665-4693) calling `self.app._dm_move_combatant_on_map(int(cid), int(col), int(row))`.
* **Existing `_actions` Mapping:** Yes. `"move"` is already defined in `LanController._ACTION_MESSAGE_TYPES` and routed via `PlayerCommandService.move`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"col": int, "row": int}` from client, mapping to `{"to": {"col": col, "row": row}, "admin_token": token}` in the queue message.
* **Expected Response Shape:** `{"ok": True, "cid": int, "col": int, "row": int, "spent_ft": int, "snapshot": Dict}`.
* **Gameplay/State Risks:** **High**.Standard rules-aware movement checks speed budgets, turn ownership (can block moves in combat if not bypassed with admin token), triggers opportunity attacks, and can trigger client prompts/warnings (like John's echo warning). Asynchronous coordination through the queue makes result and cost validation complex.
* **Focused Validation:** Requires complex test configurations to handle various movement rejection reasons.

### 3. `POST /api/dm/map/aoes/{aid}/move` (Move Map AoE)
* **Route Handler / Path:** `dm_move_aoe` in `dnd_initative_tracker.py` (lines 6300-6317) calling `self.app._dm_move_aoe_on_map(int(aid), payload)`.
* **Existing `_actions` Mapping:** Yes. `"aoe_move"` is defined in `LanController._ACTION_MESSAGE_TYPES` and calls `_handle_aoe_move_request`.
* **New Action Type Required:** No.
* **Payload Shape:** `{"col": int, "row": int, "cx": float, "cy": float, "angle_deg": float, ...}`.
* **Expected Response Shape:** `{"ok": True, "aid": int, "aoe": Dict, "snapshot": Dict}`.
* **Gameplay/State Risks:** **Low**. Modifies AoE coordinates and attributes (angle, spread). Bypasses turn rules, speed limits, and conditions.
* **Focused Validation:** Simple mock queue checks for `aoe_move`.

---

## Evaluation & Recommendation

| Candidate | Existing Queue Seam? | New Action Type? | Risk | Rationale |
| --- | --- | --- | --- | --- |
| **`POST .../place` (Reposition)** | No | Yes | **Low-Medium** | Bypasses gameplay movement rules/turns, but establishes the pattern for adding new action categories to the queue. |
| **`POST .../move` (Move)** | Yes | No | **High** | Highly coupled with gameplay state, mounts/riders, speed budgets, and prompt warnings. |
| **`POST .../aoes/{aid}/move` (Move AoE)** | Yes | No | **Low** | Global overlay mutation. Very safe, but doesn't progress combatant state isolation. |

We recommend migrating **`POST /api/dm/map/combatants/{cid}/place` (Reposition Token)** next.

Even though it requires registering a new action mapping (`place_combatant`), this candidate is the logical next step for isolating combatant modifications. By bypassing complex movement rules (opportunity attacks, speed limits), it allows us to harden the queue-adapter with minimal risk to core gameplay mechanics while establishing the standard pattern for introducing new action types to the Tk-thread queue.

---

## Proposed Next Work Item

### Proposed future work item ID
`WORK-20260629-runtime-facade-queue-command-place`

### Exact route/command to migrate
- Route: `POST /api/dm/map/combatants/{cid}/place`
- Command: `COMMAND_PLACE_COMBATANT = "place_combatant"`

### Files likely needed for that future slice
- `server_runtime.py` (Define command constant and add dispatch branch)
- `dnd_initative_tracker.py` (Update `dm_place_combatant_on_map` route to delegate via facade, register `place_combatant` action mapping, and handle it on the Tk thread)
- `tests/test_server_runtime.py` (Focused tests for `COMMAND_PLACE_COMBATANT` success, traces, and route mappings)

### Files explicitly out of scope
- `player_command_contracts.py`
- `player_command_service.py`
- Unrelated HTTP routes or combatant rules.

### Focused validation commands for that future slice
```bash
python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
.venv/bin/python -m unittest tests/test_server_runtime.py
git status --short
timeout 10s git diff --check
```

# WORK-20260629-runtime-facade-next-queue-command-selection

## Status

Completed

## Title
Runtime facade next queue command selection

## Goal
Select the next low-risk production command to route through the facade queue adapter after facing. Evidence/planning only; no app implementation.

## Strategic Lane
ASGI server first, runtime as a service.

## Source Context
This work follows:
- [WORK-20260629-runtime-facade-queue-command-facing](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-facing.md)
- [WORK-20260629-runtime-facade-queue-command-selection](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-queue-command-selection.md)
- [WORK-20260629-runtime-facade-queue-adapter](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md)

---

## Evidence Report

### 1. Mutating HTTP Routes Analyzed
We focused our analysis on the mutating HTTP routes that interact with map, tactical, or combatant state, evaluating their payload shapes, state mutations, and current queue integration.

- **`POST /api/dm/map/overlays/auras` (Auras Overlay Toggle)**
  - *Payload:* `{"enabled": bool}`
  - *State Mutation:* Updates `_lan_auras_enabled` flag and forces a state broadcast. Bypasses all combatant, turn, speed, and hazard rules.
  - *Queue Mapping:* Already maps natively to the existing `"set_auras_enabled"` message type in `UTILITY_ADMIN_COMMAND_TYPES` and the `"set_auras_enabled"` handler in `PlayerCommandService`.
  - *Risk:* **Extremely Low**. Global presentation layer toggle with no gameplay mechanics dependencies.

- **`POST /api/dm/map/combatants/{cid}/place` (Reposition Token)**
  - *Payload:* `{"col": int, "row": int}`
  - *State Mutation:* Relocates token on map, checking destination cell availability. Bypasses movement speed remaining, path obstacles, and turn checks.
  - *Queue Mapping:* **None**. Bypasses the LAN action queue. Migrating this would require modifying `_lan_apply_action` to add a new `"place_combatant"` action type.
  - *Risk:* **Low-Medium**. Touches coordinate validation, rider/mount position sync, and fixed-to-caster AOEs, but is admin-only.

- **`POST /api/dm/map/combatants/{cid}/move` (Rules-Aware Move)**
  - *Payload:* `{"col": int, "row": int}`
  - *State Mutation:* Updates coordinate positions, consumes movement budget, triggers environmental hazard damage, checks turn permissions, and handles hidden movement.
  - *Queue Mapping:* Maps cleanly to `"move"` in `MOVEMENT_ACTION_COMMAND_TYPES` and is processed by `PlayerCommandService.move`.
  - *Risk:* **Medium-High**. Highly coupled with active gameplay combat states, mounts/riders, speed budgets, and hazard triggers.

---

## Evaluation of Next Migration Options

### Option A: `POST /api/dm/map/overlays/auras` (Recommended)
- **Rationale:**
  - Already defined in the allowed list `UTILITY_ADMIN_COMMAND_TYPES`.
  - Already has a dispatcher and handler `set_auras_enabled` in `PlayerCommandService` and `dnd_initiative_tracker.py`.
  - Minimizes moving parts: We only need to wire the HTTP route to the facade queue adapter and add the command constant.
  - Serves as a perfect low-risk follow-up to `set_facing` to harden global settings/overlays.
- **Risk Mitigation:** Bypasses all turn rules and combatant conditions.

### Option B: `POST /api/dm/map/combatants/{cid}/move` (Alternative)
- **Rationale:**
  - Core mutating tactical map action.
  - Already mapped in `MOVEMENT_ACTION_COMMAND_TYPES` and `PlayerCommandService.move`.
- **Risks:**
  - Highly complex. Any failure in path calculation or movement budget raises validation errors that must be safely mapped.
  - In combat, turn validation could block movements if not carefully bypassed via `is_admin=True` admin tokens.
  - Movement triggers environmental damage / triggers which can execute nested code paths.

---

## Recommendation
We recommend **Option A: `POST /api/dm/map/overlays/auras`** (`set_auras_enabled`) as the next logical, low-risk queue-backed command. It continues the path of extracting simple administrative/presentation mutations, cementing the stability of the queue-adapter interface with zero risk to gameplay.

---

## Proposed Next Work Item

### Proposed next work item ID
`WORK-20260629-runtime-facade-queue-command-auras`

### Proposed goal
Migrate the `POST /api/dm/map/overlays/auras` endpoint to execute through the `ServerRuntimeFacade` using the queue adapter seam.

### Files to inspect first
- [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py) (lines 6335-6359: `dm_set_auras_overlay` route, and lines 42841-42860: `_handle_set_auras_enabled_request`)
- [server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/server_runtime.py) (registering `COMMAND_SET_AURAS_ENABLED`)
- [tests/test_server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_server_runtime.py)

### Allowed files to edit
- [server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/server_runtime.py)
- [tests/test_server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_server_runtime.py)
- [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)

### Forbidden scope
- Do not migrate any other FastAPI routes.
- Do not modify gameplay, combat, or movement mechanics.
- Do not touch logs/context/ or unrelated bug queues.

### Validation commands
```bash
python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
.venv/bin/python -m unittest tests/test_server_runtime.py
git status --short
timeout 10s git diff --check
```

### Close criteria
1. `POST /api/dm/map/overlays/auras` is successfully routed through `self._runtime.submit_command` using `COMMAND_SET_AURAS_ENABLED = "set_auras_enabled"`.
2. Unit tests verify that `COMMAND_SET_AURAS_ENABLED` is processed through the queue adapter, enqueued to `LanController._actions`, executed on the Tk thread, and updates state.
3. No other routes are migrated and gameplay behavior is preserved.
4. Validation commands pass.

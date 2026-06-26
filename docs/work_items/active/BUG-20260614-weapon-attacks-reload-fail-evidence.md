# BUG-20260614-weapon-attacks-reload-fail Evidence

## Scope
This phase was for evidence capture and classification only. No implementation was performed.

## Sources inspected
The following sources were inspected:
- [docs/work_items/current_work.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/current_work.md)
- [docs/work_items/active/BUG-20260614-weapon-attacks-reload-fail.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/active/BUG-20260614-weapon-attacks-reload-fail.md)
- [docs/bug_reports/triaged/BUG-20260614-weapon-attacks-reload-fail.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/bug_reports/triaged/BUG-20260614-weapon-attacks-reload-fail.md)
- [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py) (specifically weapon reload, equipped inventory sync, and attack adjudication functions)
- [tests/test_firearm_reload.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_firearm_reload.py)
- [tests/test_items_weapon_resolution.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_items_weapon_resolution.py)
- All log/trace files in the `logs/` directory.

## Evidence found
1. **Weapon Reload Routing Defect**:
   - In [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py#L42817-L43135), the incoming websocket message routing method `_lan_apply_action` has cases for several action types (e.g., `attack_request`, `use_consumable`), but completely lacks a case for the `"reload_weapon"` action type.
   - When the client frontend clicks the "Reload" button, it transmits `send({type: "reload_weapon", ...})` over the websocket (as seen in `assets/web/lan/index.html`). On the server side, this message is received by `_lan_apply_action` and silently ignored/dropped instead of being dispatched to `PlayerCommandService.reload_weapon`.
   - Functional tests in `tests/test_firearm_reload.py` (which invoke `PlayerCommandService.reload_weapon` directly) pass successfully, proving the backend reload logic itself is correct but simply unreachable via the websocket channel.

2. **Equipped Weapon Normalization Ordering Defect (Saber Attack Link)**:
   - In `_normalize_player_profile` in [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py#L27353-L27378), equipped weapons synced from the player's inventory are appended to `normalized_weapons` *after* the primary weapon loop runs.
   - Because they are added late, inventory-equipped weapons (such as a "saber" equipped via the inventory tab) bypass critical normalization steps (such as ensuring default/fallback `to_hit` values are populated, properties are formatted, and attack modes are canonicalized).
   - If an attack request is resolved in `_adjudicate_attack_request` with an un-normalized weapon, the absence or incorrect formatting of these properties can cause resolution failures or incorrect default behaviors.

## Evidence not found
- No recent log or trace files (`logs/live-debug-console*.log` or `logs/debug-trace-*.jsonl`) from the time of the reported bug (June 14th onward) contain any error records, track events, or tracebacks mentioning `"saber"` or `"reload"`.
- There is no weapon definition file for `"saber"` in the repository (e.g. under `Items/` registry). It is likely a custom item defined inline in a player profile or manually added.

## Code/data areas implicated
1. `InitiativeTracker._lan_apply_action` in [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py#L42817) (missing routing case for `"reload_weapon"`).
2. `InitiativeTracker._normalize_player_profile` in [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py#L27141) (ordering of inventory-equipped weapon synchronization and normalization).

## Classification
- **split into separate reload and saber bugs**
  - **Reason**: The firearm reload failure and the saber attack failure have completely different root causes and execution paths:
    1. Reloading fails because of a missing websocket route handler in `_lan_apply_action`.
    2. Saber/melee attacks fail due to weapon properties bypassing normalization when synchronized from the inventory equipped slot in `_normalize_player_profile`.

## Recommended next action
Implement a follow-up fix task to (1) route `"reload_weapon"` in `_lan_apply_action` to `PlayerCommandService.reload_weapon` and (2) normalize inventory-synced equipped weapons correctly inside `_normalize_player_profile`.

## Validation
```bash
git status --short
timeout 10s git diff --check
```
(No modifications outside the evidence document itself, and check runs clean.)

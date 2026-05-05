# Firearm Subsystem Implementation Plan

This document outlines the repo-grounded implementation plan for the firearm subsystem in init-tracker.

## 1. Repo findings

### 1.1 Item/equipment model
- Weapons are defined in YAML files under `Items/Weapons/`.
- Players have an `inventory` section in their YAMLs under `players/`.
- Items in inventory have an `instance_id` (e.g., `hellfire_battleaxe_plus_2__001`).
- The tracker resolves weapons from a registry using `_resolve_weapon_from_items`.
- Item state persistence is handled by loading, modifying, and saving player YAMLs (see `_mutate_owned_inventory_...` methods in `dnd_initative_tracker.py`).

### 1.2 Attack execution
- `InitiativeTracker._adjudicate_attack_request` (L35859) is the primary path for weapon attacks.
- It already handles `weapon_id`, `weapon_name`, and `weapon` (inline data).
- It checks range using map positions if available.
- It handles action economy (Action, Bonus Action, Reaction).

### 1.3 Action economy
- The repo tracks `action_remaining`, `bonus_action_remaining`, and `reaction_remaining` on the `Combatant` class.
- Firearms will need to hook into these for `Reload` (Bonus Action) and `Aimed Shot` (Action).

### 1.4 Conditions/states/resources
- There is a robust condition system (`ConditionStack`).
- Noise/Loud events are not yet implemented.
- Jammed, Braced, and Suppressed states are not yet implemented.

### 1.5 UI
- The DM console and player UI interact with the backend via `PlayerCommandService`.
- Weapon modes (one-handed/two-handed) are already supported in the UI and backend.

## 2. Current model gaps

| Primitive | Status | Requirement |
| :--- | :--- | :--- |
| `ammo_current` / `ammo_max` | Missing | Blocking for Firearms |
| `Reload` command | Missing | Blocking for Firearms |
| `Loud` event log marker | Missing | Blocking for Firearms |
| `Sidearm` property logic | Missing | Deferrable (can be handled manually in v1) |
| `Braced` state | Missing | Deferrable |
| `Suppressed` condition | Missing | Deferrable |
| `Jam` logic | Missing | Deferrable |

## 3. Firearm v1 recommendation

A precise minimal playable scope:
- **Items:** .45 Service Pistol, Armalite Rifle.
- **State:** `ammo_current`, `ammo_max` on item instances.
- **Actions:** Single Shot (spend 1 ammo), Reload (reset ammo to max).
- **Log:** "Loud" marker on discharge.
- **Content:** Black and Tan Constable and Rifleman.

## 4. Proposed data shapes

### 4.1 .45 Service Pistol (Item Definition)
```yaml
id: p45_service_pistol
name: .45 Service Pistol
category: simple_ranged
weapon_group: Firearms
range: 40/120
to_hit: 0
one_handed:
  damage_formula: 1d8 + dex_mod
  damage_type: piercing
properties:
- sidearm
- loud
- magazine_8
mastery: vex
```

### 4.2 Armalite Rifle (Item Definition)
```yaml
id: armalite_rifle
name: Armalite Rifle
category: martial_ranged
weapon_group: Firearms
range: 100/400
to_hit: 0
one_handed:
  damage_formula: 1d10 + dex_mod
  damage_type: piercing
properties:
- loud
- magazine_20
mastery: push
```

### 4.3 Item Instance State (in player/monster YAML)
```yaml
- id: p45_service_pistol
  instance_id: p45_service_pistol__001
  name: .45 Service Pistol
  equipped: true
  slot: main_hand
  ammo_current: 8
  ammo_max: 8
```

### 4.4 Black and Tan Constable (Monster YAML)
```yaml
name: Black and Tan Constable
type: Humanoid
ac: 14 (Padded Armor)
hp: 18
speed: 30 ft.
abilities:
  Str: 12
  Dex: 14
  Con: 12
  Int: 10
  Wis: 11
  Cha: 10
actions:
- name: .45 Service Pistol
  desc: "Ranged Weapon Attack: +4 to hit, range 40/120 ft., one target. Hit: 6 (1d8 + 2) piercing damage. Loud. Magazine 8."
- name: Baton
  desc: "Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 3 (1d4 + 1) bludgeoning damage."
```

## 5. Implementation sequence

### Pass A: Firearm item definitions + ammo state support (COMPLETED)
- **Files changed:** `dnd_initative_tracker.py`, `Items/Weapons/p45_service_pistol.yaml`, `Items/Weapons/armalite_rifle.yaml`.
- **Status:** Core backend support for `ammo_current`, `ammo_max`, and `ammo_type` implemented.
- **Implemented Fields:**
  - `ammo_current`: Current loaded shots.
  - `ammo_max`: Magazine capacity (can be parsed from `magazine_X` property).
  - `ammo_type`: Abstract ammunition type.
  - `loud`: Property that triggers an info log message on firing.
- **Tests:** `tests/test_firearm_ammo_v1.py` verifies decrementing, blocking empty weapons, and Loud logging.

### Pass B: Single Shot + Reload backend (COMPLETED)
- **Files changed:** `dnd_initative_tracker.py`, `player_command_service.py`, `player_command_contracts.py`.
- **Status:** Backend support for reloading and ammo decrement on attack implemented.
- **Implemented Functionality:**
  - `_adjudicate_attack_request` decrements `ammo_current` on firearm discharge.
  - `InitiativeTracker._mutate_owned_inventory_weapon_reload` resets `ammo_current` to `ammo_max`.
  - `PlayerCommandService.reload_weapon` provides the authoritative entry point.
  - Command Shape:
    ```json
    {
      "type": "reload_weapon",
      "item_instance_id": "<instance_id>"
    }
    ```
- **Tests:** `tests/test_firearm_reload.py` verifies reload logic and service dispatch.

### Pass C: Player/DM UI ammo display and controls (PARTIAL - LAN landed)
- **Files changed:** `assets/web/lan/index.html`.
- **Status:** LAN UI now shows ammo status and provides a Reload button for firearms.
- **Implemented Functionality (LAN):**
  - Ammo status display (`Ammo: current/max`) below Main Hand and Off-Hand selectors.
  - "Reload" buttons that dispatch the `reload_weapon` command.
  - Automatic UI refresh via state broadcast after reload or attack.
  - Conditional display: only weapons with ammo metadata show the status/reload UI.
- **Tests:** `tests/test_lan_firearm_ui.py` verifies the presence of UI elements and helper logic.

### Pass D: Black and Tan Constable/Rifleman content
- **Files to change:** `Monsters/black_and_tan_constable.yaml`, `Monsters/black_and_tan_rifleman.yaml`.
- **Tasks:**
  - Create the YAML files for the new enemies.
  - Verify they load and their attacks work.

### Pass E: Live browser smoke and bugfixes
- **Tasks:**
  - Full end-to-end test in a browser.
  - Fix any UI/backend sync issues.

## 6. Deferred features
- **SAM-7:** Needs area template and heavy ordnance logic.
- **Suppressive Fire / Automatic Sweep:** Needs complex area handling and multi-target logic.
- **Overwatch:** Needs reaction trigger integration.
- **Jammed / Braced:** Needs new conditions and UI markers.

## 7. Fastest next coding task
The first task should be adding ammo state support to the item loader and attack adjudicator.

```python
# In InitiativeTracker._adjudicate_attack_request:
# After resolving selected_weapon:
ammo_current = _parse_int(selected_weapon.get("ammo_current"))
if ammo_current is not None and ammo_current <= 0:
    self._lan.toast(ws_id, "Weapon is empty! Reload, matey.")
    return

# After resolving hit/miss:
if ammo_current is not None:
    # Logic to decrement ammo and update inventory...
```

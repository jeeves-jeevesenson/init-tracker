# living_firearm_plans.md

Status: Living implementation plan  
Project: init-tracker  
Audience: DM, coding agents, future maintainers  
Feature area: Firearms, ammunition, fire modes, suppression, and heavy ordnance  
Primary item names: **Armalite Rifles**, **.45 Pistols**, **SAM-7 Missiles**

---

## 0. Working principle

This document defines a D&D 2024-compatible firearm subsystem for init-tracker.

The design goal is not real-world simulation. The goal is a tactical TTRPG implementation that feels different from bows and crossbows while staying compatible with D&D combat math, HP, AC, saving throws, Weapon Mastery, conditions, reactions, cover, and map templates.

Core rule:

```text
Firearms do not bypass HP.
Firearms do not auto-kill.
Firearms create tactical pressure through range, ammunition, reloads, fire modes, cover, suppression, noise, and rare heavy ordnance.
```

This is intentionally a **game system**, not a real-world weapons manual. Do not add real-world operational procedures, real-world missile behavior, manufacturing data, maintenance data, or detailed technical specifications. Keep all implementation details scoped to fantasy tabletop mechanics.

---

## 1. Intended gameplay outcome

At the table, firearms should do these things:

1. Make cover and line-of-sight matter more.
2. Give martials and trained NPCs strong ranged tactical options.
3. Create meaningful action economy decisions through reloads, aiming, bracing, and fire modes.
4. Make automatic fire feel different without creating ten separate attack rolls.
5. Make heavy ordnance feel like a rare set-piece tool, not a repeatable default attack.
6. Keep D&D 2024 combat recognizable.
7. Fit init-tracker’s existing action/condition/map/event-log style.

Firearms should **not** do these things:

1. Ignore armor by default.
2. Ignore monster durability.
3. Replace class features.
4. Turn every combat into save-spam.
5. Require per-bullet simulation.
6. Require complex real-world firearm knowledge.
7. Require major engine rewrites before a playable v1.

---

## 2. Current design assumptions

These assumptions should be verified against the actual repo before coding.

The implementation plan assumes init-tracker has or can support:

- Characters, monsters, and NPC combatants.
- Weapons/items attached to actors.
- Attack rolls.
- Saving throws.
- Damage rolls.
- Conditions/effects with durations.
- Action, Bonus Action, Reaction tracking or at least action-cost metadata.
- Tactical map coordinates and area templates, or planned support for them.
- Event log/combat log output.
- DM-facing item/content authoring or JSON-backed content import.
- Some form of weapon properties/tags.
- Some form of per-item state, or at minimum actor inventory state.

If any assumption is false, agents should adapt the plan by adding the smallest missing primitive first rather than flattening firearm rules into one-off hardcoded behavior.

---

## 3. Naming rules

Use the user’s names directly:

- **Armalite Rifles**
- **.45 Pistols**
- **SAM-7 Missiles**

Do not replace them with fictional substitutes such as “Sky-Hunter,” “light rifle,” or “fantasy missile.”

It is acceptable to use subtypes where needed, but the visible family name should remain intact.

Examples:

```text
Armalite Rifle
Armalite Battle Rifle
Armalite Precision Rifle
Armalite Automatic Rifle
.45 Service Pistol
.45 Heavy Pistol
.45 Compact Pistol
SAM-7 Launcher
SAM-7 Missile
```

Avoid adding real-world manufacturer/model-specific detail. These should remain tabletop abstractions.

---

## 4. Rules package overview

The firearm subsystem has three implementation phases.

### Phase 1: Core firearms

Minimum playable implementation.

Includes:

- Magazine ammunition tracking.
- Reload action.
- Loud event tag.
- Sidearm property.
- Single Shot.
- Aimed Shot.
- Controlled Burst.
- Jammed weapon state.
- Basic Armalite Rifles and .45 Pistols.

### Phase 2: Tactical fire

Adds map pressure and tactical gameplay.

Includes:

- Braced condition/state.
- Automatic Sweep.
- Suppressive Fire.
- Suppressed condition.
- Overwatch.
- Area templates for cone/line/cube if not already present.
- Better event log messages.

### Phase 3: Heavy ordnance

Adds rare set-piece weapons.

Includes:

- SAM-7 Launcher.
- SAM-7 Missile ammunition.
- Heavy Ordnance proficiency gate.
- Lock-On action.
- Fire Missile action.
- Blast area.
- Missile consumption.
- Counterplay via cover, obscurity, magic, and target movement.

---

## 5. Core mechanical vocabulary

### 5.1 Magazine X

A weapon with `Magazine X` holds X shots.

Rules text:

```text
Magazine X.
This weapon holds X shots. Each attack or fire mode spends ammunition. If the weapon does not have enough ammunition for the selected fire mode, that mode cannot be used.
```

Implementation requirements:

- Track current ammo per weapon instance, not just weapon definition.
- Display current ammo in the combat UI.
- Decrement ammo when a fire mode is executed.
- Prevent firing when ammo is insufficient.
- Allow reload only if actor has compatible spare ammo or if the DM override is used.
- Preserve ammo state across turns and ideally across saved sessions.

Suggested instance state:

```json
{
  "item_instance_id": "uuid",
  "definition_id": "armalite_rifle_standard",
  "ammo_current": 20,
  "ammo_max": 20,
  "ammo_type": "rifle_round",
  "weapon_states": []
}
```

### 5.2 Reload

Rules text:

```text
Reload.
A proficient wielder can reload this weapon as a Bonus Action if they have a free hand and compatible ammunition ready. A nonproficient wielder reloads it as an Action.
```

Implementation requirements:

- Add a `Reload` button for firearms with magazine state.
- Determine action cost from proficiency when possible.
- If free-hand logic does not exist yet, do not block v1 on it. Log a reminder or expose a DM override.
- Set `ammo_current = ammo_max` or consume an ammo bundle/magazine item if inventory supports it.
- Event log should show old and new ammo values.

Example log:

```text
A2-Jeeves reloads Armalite Rifle. Ammo: 3/20 → 20/20. Bonus Action used.
```

### 5.3 Loud

Rules text:

```text
Loud.
Firing this weapon reveals the shooter’s location to creatures that can hear the shot. The shot is audible out to at least 300 feet in ordinary conditions, and farther in quiet, enclosed, or magically amplified terrain.
```

Implementation requirements:

- Do not attempt complex sound propagation in v1.
- Add an event-log marker when a Loud weapon is fired.
- Optionally expose a DM-facing “Noise Event” marker on the encounter/map.
- This should be metadata-driven, not hardcoded to specific weapons.

Suggested event payload:

```json
{
  "type": "noise_event",
  "source_actor_id": "actor_uuid",
  "source_item_id": "item_uuid",
  "label": "Loud firearm discharge",
  "audible_range_ft": 300,
  "reveals_source": true
}
```

### 5.4 Sidearm

Rules text:

```text
Sidearm.
If proficient, you do not suffer Disadvantage for making ranged attacks with this weapon while a hostile creature is within 5 feet of you.
```

Implementation requirements:

- This modifies the usual ranged-attack-in-melee disadvantage rule.
- It only applies when the actor is proficient with the weapon.
- It should be property-driven so it can be reused later.

### 5.5 Braced

Rules text:

```text
Braced.
You are Braced if you have not moved this turn, are prone, are behind Half Cover or better, or used a Bonus Action to Brace. The Braced state lasts until the start of your next turn unless a specific rule says otherwise.
```

Implementation requirements:

- Phase 1 can skip this if movement tracking is not ready.
- Phase 2 should add this as a temporary actor state.
- Braced should be visible on the token or actor card.
- A manual `Brace` button should exist for the DM/player even if automatic detection is incomplete.

Suggested state:

```json
{
  "id": "braced",
  "name": "Braced",
  "type": "temporary_state",
  "duration": {
    "ends_at": "start_of_source_next_turn"
  },
  "source": "manual_bonus_action"
}
```

---

## 6. Fire modes

Fire modes are the heart of the system.

Implementation design:

```text
Weapon Definition → Available Fire Modes → Chosen Mode → Validation → Ammo Spend → Attack/Save/Template → Damage/Effects → Jam Check → Event Log
```

Each fire mode should be defined as data where possible.

Suggested generic fire mode shape:

```json
{
  "id": "controlled_burst",
  "name": "Controlled Burst",
  "requires_properties": ["burst"],
  "action_cost": "attack_modifier",
  "ammo_cost": 3,
  "resolution": "attack_roll",
  "damage_mode": "weapon_damage_plus_extra_die",
  "limit": "once_per_turn",
  "jam_risk": true
}
```

---

## 7. Fire mode: Single Shot

Rules text:

```text
Single Shot.
Make a ranged weapon attack. Spend 1 ammo. On a hit, deal the weapon’s normal damage.
```

Purpose:

- Default firearm attack.
- Compatible with Extra Attack.
- Compatible with normal attack roll logic.
- Compatible with Weapon Mastery.

Implementation requirements:

- Spend 1 ammo per attack.
- Use normal ranged weapon attack flow.
- Use normal damage flow.
- Apply weapon mastery if applicable.
- Trigger Loud event if weapon has Loud.
- Check for insufficient ammo before roll.

Pseudo-flow:

```text
on_fire_mode_selected(single_shot):
  validate weapon has ammo_current >= 1
  validate actor can make attack
  spend 1 ammo
  roll attack
  resolve hit/miss
  on hit: roll weapon damage + ability modifier where applicable
  apply mastery if applicable
  emit Loud event if weapon has loud
  log result
```

Suggested event log:

```text
A2-Jeeves fires .45 Service Pistol: Single Shot.
Ammo: 8/8 → 7/8.
Attack 19 hits Goblin Captain.
Damage: 1d10 + 5 piercing.
Loud event created.
```

---

## 8. Fire mode: Aimed Shot

Rules text:

```text
Aimed Shot.
As a Bonus Action, aim with a firearm you are wielding. Before the end of your turn, your next Single Shot with that weapon gains one of the following benefits:

- Ignore Half Cover.
- Ignore Disadvantage from long range.
- Add +1d6 damage on a hit.

You lose this benefit if you move before making the attack.
```

Purpose:

- Gives tactical ranged characters a useful Bonus Action.
- Rewards staying still.
- Interacts cleanly with cover and long range.
- Does not add another independent attack.

Implementation requirements:

- Aimed Shot should create a temporary actor/weapon state.
- The state should bind to a specific weapon instance where possible.
- The player/DM must choose one benefit.
- The state expires after the next Single Shot, movement, or end of turn.
- The `+1d6 damage` option should only apply on hit.

Suggested state:

```json
{
  "id": "aimed_shot_pending",
  "name": "Aimed Shot",
  "source_actor_id": "actor_uuid",
  "source_item_id": "weapon_uuid",
  "chosen_benefit": "extra_damage_1d6",
  "expires": ["after_next_single_shot", "on_source_moves", "end_of_source_turn"]
}
```

Suggested UI:

```text
[Aim]
  Choose benefit:
    ( ) Ignore Half Cover
    ( ) Ignore long-range Disadvantage
    ( ) +1d6 damage on hit
```

Acceptance criteria:

- Aimed Shot consumes Bonus Action when action tracking exists.
- The benefit applies to only one Single Shot.
- Moving before firing clears the pending state if movement tracking exists.
- If movement tracking does not exist, the UI should show a DM reminder.

---

## 9. Fire mode: Controlled Burst

Rules text:

```text
Controlled Burst.
When you make a firearm attack with a weapon that has the Burst property, you can spend 3 ammo before the attack roll. On a hit, the attack deals one extra weapon damage die.

You can benefit from Controlled Burst only once per turn.
```

Purpose:

- Makes Armalite Rifles feel different from bows.
- Adds a high-value shot without multiplying attacks.
- Gives ammo pressure.
- Keeps DPR in a sane level 11 range.

Implementation requirements:

- Requires weapon property `burst`.
- Requires at least 3 ammo.
- Spends 3 ammo whether the attack hits or misses.
- Adds one extra weapon damage die on hit.
- Does not add the ability modifier again.
- Limited to once per actor turn.
- Has Jam Risk.

Example damage behavior:

```text
Armalite Rifle: 1d12 + Dex
Controlled Burst hit: 2d12 + Dex

Armalite Battle Rifle: 2d6 + Dex
Controlled Burst hit: 3d6 + Dex
```

Suggested state for once-per-turn limit:

```json
{
  "turn_flags": {
    "controlled_burst_used": true
  }
}
```

Suggested event log:

```text
A2-Jeeves fires Armalite Rifle: Controlled Burst.
Ammo: 20/20 → 17/20.
Attack 23 hits Ogre Veteran.
Damage: 2d12 + 5 piercing.
Loud event created.
```

Acceptance criteria:

- Controlled Burst appears only for weapons with `burst`.
- It cannot be selected if ammo is below 3.
- It cannot be used more than once per turn by the same actor.
- Extra damage die uses the weapon’s base die, not a hardcoded die.
- Natural 1 can trigger Jammed after resolution.

---

## 10. Fire mode: Automatic Sweep

Rules text:

```text
Automatic Sweep.
As an Action, choose a 15-foot cone or a 30-foot line within the weapon’s normal range. Spend 10 ammo. Each creature in the area must make a Dexterity saving throw.

Save DC = 8 + your Proficiency Bonus + your Dexterity modifier.

On a failed save, a creature takes the weapon’s normal damage without your Dexterity modifier.
On a successful save, it takes no damage.

Creatures behind Half Cover have Advantage on the save. Creatures behind Three-Quarters Cover automatically succeed.
```

Purpose:

- Full-auto feel without rolling many attacks.
- Converts automatic fire into area denial and multi-target pressure.
- Trades Extra Attack for a single Action.
- Makes cover extremely relevant.

Implementation requirements:

- Requires weapon property `auto`.
- Requires at least 10 ammo.
- Uses full Action, not one attack inside Attack action.
- Requires map template selection if map support exists.
- Template options: 15-foot cone or 30-foot line.
- Targets all creatures in template, subject to DM filtering.
- Save is Dexterity.
- DC uses actor proficiency and Dex modifier by default.
- No Dex modifier added to damage.
- Half Cover gives Advantage on save.
- Three-Quarters Cover auto-succeeds.
- Total Cover excludes target.
- Has Jam Risk.

Suggested fire mode data:

```json
{
  "id": "automatic_sweep",
  "name": "Automatic Sweep",
  "requires_properties": ["auto"],
  "action_cost": "action",
  "ammo_cost": 10,
  "resolution": "area_save",
  "template_options": [
    { "type": "cone", "size_ft": 15 },
    { "type": "line", "length_ft": 30, "width_ft": 5 }
  ],
  "save": {
    "ability": "dexterity",
    "dc_formula": "8 + proficiency_bonus + dexterity_modifier"
  },
  "damage": {
    "formula": "weapon_base_damage",
    "include_ability_modifier": false,
    "save_success": "none"
  },
  "cover_interactions": {
    "half_cover": "advantage_on_save",
    "three_quarters_cover": "automatic_success",
    "total_cover": "not_targeted"
  },
  "jam_risk": true
}
```

Acceptance criteria:

- Automatic Sweep does not multiply by Extra Attack.
- It cannot be selected if ammo is below 10.
- It spends ammo before saves are rolled.
- Save DC is displayed before resolution.
- Damage excludes ability modifier.
- Cover effects are visible or at least logged.

---

## 11. Fire mode: Suppressive Fire

Rules text:

```text
Suppressive Fire.
As an Action, choose a 10-foot cube within the weapon’s normal range. Spend 10 ammo. Until the start of your next turn, the area is Suppressed.

The first time a hostile creature starts its turn in the area or enters it, it must make a Wisdom saving throw.

Save DC = 8 + your Proficiency Bonus + your Dexterity modifier.

On a failed save, the creature gains the Suppressed condition until the end of its turn.
On a successful save, it is unaffected.

Creatures immune to the Frightened condition have Advantage on this save.
Creatures behind Total Cover are unaffected.
```

Purpose:

- This is the main mechanic that makes firearms feel like firearms.
- It changes movement behavior without requiring high damage.
- It gives NPC squads real tactical identity.
- It gives players a reason to use cover, prone, fog, silence, walls, forced movement, or flanking.

Implementation requirements:

- Requires weapon property `auto`.
- Requires at least 10 ammo.
- Uses full Action.
- Creates a temporary area effect on the map.
- Area: 10-foot cube.
- Duration: until start of shooter’s next turn.
- Trigger: hostile starts turn in area or enters area.
- Save: Wisdom.
- Failed save applies Suppressed until end of that creature’s turn.
- Frightened immunity grants Advantage, but does not auto-ignore.
- Total Cover prevents effect.
- Has Jam Risk.

Suggested area effect data:

```json
{
  "id": "suppressed_area_uuid",
  "type": "area_effect",
  "name": "Suppressive Fire",
  "source_actor_id": "actor_uuid",
  "source_item_id": "weapon_uuid",
  "shape": {
    "type": "cube",
    "size_ft": 10
  },
  "duration": {
    "ends_at": "start_of_source_next_turn"
  },
  "trigger": {
    "events": ["target_starts_turn_in_area", "target_enters_area"],
    "once_per_target_per_area": true
  },
  "save": {
    "ability": "wisdom",
    "dc_formula": "8 + source.proficiency_bonus + source.dexterity_modifier"
  },
  "on_failed_save": {
    "apply_condition": "suppressed",
    "duration": "end_of_target_turn"
  }
}
```

Acceptance criteria:

- Suppressive Fire creates a visible area effect if map support exists.
- The area expires at the correct turn boundary.
- Each target is affected at most once per area instance unless the DM manually reruns it.
- It uses Wisdom saves, not Dexterity saves.
- It does not deal damage by default.
- It logs ammo spend and area creation.

---

## 12. Condition: Suppressed

Rules text:

```text
Suppressed.
Until the condition ends, the creature has Disadvantage on the next attack roll it makes, and its speed is reduced by 10 feet.

The condition ends early if the creature drops prone, moves behind cover, or uses its Action to steady itself.
```

Purpose:

- Low-bookkeeping pressure condition.
- Avoids hard crowd control.
- Does not stack into permanent lockdown.
- Lets affected creatures choose tactical responses.

Implementation requirements:

- Apply to actor, not weapon.
- Duration usually ends at end of affected actor’s turn.
- Disadvantage applies only to next attack roll, then the attack penalty part is consumed.
- Speed penalty remains until condition ends.
- Manual remove button should exist.
- Auto-ending from prone/cover/action can be added incrementally.

Suggested condition definition:

```json
{
  "id": "suppressed",
  "name": "Suppressed",
  "category": "combat_condition",
  "stacking": "refresh_duration",
  "effects": [
    {
      "id": "suppressed_next_attack_disadvantage",
      "type": "attack_roll_disadvantage",
      "limit": "next_attack_roll",
      "consume_on_use": true
    },
    {
      "id": "suppressed_speed_penalty",
      "type": "speed_modifier",
      "amount": -10
    }
  ],
  "manual_end_options": [
    "drop_prone",
    "move_behind_cover",
    "use_action_to_steady"
  ]
}
```

UI behavior:

```text
Suppressed
- Disadvantage on next attack roll
- Speed -10 ft
- Ends at end of turn
Buttons: [Drop Prone & Clear] [Use Action to Steady & Clear] [DM Clear]
```

Acceptance criteria:

- The condition is visible.
- The next attack disadvantage is consumed after one attack.
- Speed reduction is displayed.
- End-of-turn cleanup works.
- Manual clear works.

---

## 13. Fire mode: Overwatch

Rules text:

```text
Overwatch.
As an Action, choose a visible 30-foot line, 15-foot cone, doorway, corridor, or similar firing lane within your weapon’s normal range. Until the start of your next turn, you can use your Reaction to make one Single Shot against a creature that enters or moves through that lane.

The shot occurs before the creature leaves the chosen lane.
```

Purpose:

- Gives firearm users a tactical held-action mode.
- Makes corridors, doors, and chokepoints matter.
- Works naturally with maps.
- Gives init-tracker a useful reaction prompt.

Implementation requirements:

- Requires firearm with ammo >= 1.
- Uses Action to set up.
- Creates temporary area/lane marker.
- Consumes Reaction when triggered and fired.
- Resolves as Single Shot.
- Expires at start of source actor’s next turn.
- DM can manually trigger if automatic movement trigger is not available.

Suggested state:

```json
{
  "id": "overwatch_uuid",
  "type": "reaction_ready_area",
  "name": "Overwatch",
  "source_actor_id": "actor_uuid",
  "source_item_id": "weapon_uuid",
  "duration": {
    "ends_at": "start_of_source_next_turn"
  },
  "trigger": {
    "events": ["creature_enters_area", "creature_moves_through_area"],
    "requires_reaction": true
  },
  "reaction": {
    "fire_mode": "single_shot",
    "ammo_cost": 1
  }
}
```

Acceptance criteria:

- Overwatch creates visible pending state.
- It expires correctly.
- It cannot fire if the actor has no Reaction available when reaction tracking exists.
- It spends ammo only when the reaction shot fires, not when Overwatch is set.
- Manual trigger works for v1 if automatic movement triggers are not ready.

---

## 14. Jammed weapon state

Rules text:

```text
Jam Risk.
A firearm only risks jamming when using Controlled Burst, Automatic Sweep, or Suppressive Fire.

If the attack roll is a natural 1, or if every target succeeds against Automatic Sweep or Suppressive Fire, the weapon becomes Jammed after the action resolves.

Jammed.
A Jammed firearm cannot be fired. A proficient wielder can clear the jam as a Bonus Action. A nonproficient wielder clears it as an Action.
```

Purpose:

- Adds firearm texture.
- Avoids punishing every natural 1 from normal attacks.
- Avoids making high-attack martials hate firearms.
- Creates a cost for burst/auto modes.

Implementation requirements:

- Jammed is a weapon state, not an actor condition.
- A Jammed weapon cannot use any fire mode.
- UI should show `Jammed` on weapon panel.
- `Clear Jam` button should appear.
- Action cost depends on proficiency.
- Jam check occurs after action resolution, not before.

Suggested state:

```json
{
  "weapon_states": [
    {
      "id": "jammed",
      "name": "Jammed",
      "applies_to": "weapon_instance",
      "blocks_fire_modes": true,
      "clear_action_cost": {
        "proficient": "bonus_action",
        "nonproficient": "action"
      }
    }
  ]
}
```

Acceptance criteria:

- Jammed blocks firing.
- Reloading does not automatically clear Jammed unless DM explicitly allows it.
- Clear Jam removes the state and logs the action cost.
- Controlled Burst can jam on natural 1.
- Automatic Sweep/Suppressive Fire can jam if all targets succeed or if the DM marks the area as no meaningful effect.

---

## 15. Weapon family: .45 Pistols

All .45 Pistols are martial ranged firearms unless the campaign defines a separate firearm proficiency.

### 15.1 .45 Service Pistol

Rules definition:

```text
.45 Service Pistol
Martial Ranged Weapon
Damage: 1d10 piercing
Range: 40/120
Magazine: 8
Properties: Ammunition, Magazine 8, Reload, Sidearm, Loud
Mastery: Vex
Fire Modes: Single Shot, Aimed Shot, Overwatch
```

Suggested data:

```json
{
  "id": "pistol_45_service",
  "name": ".45 Service Pistol",
  "family": ".45 Pistols",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "1d10",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 40,
    "long_ft": 120
  },
  "ammo": {
    "type": "pistol_45_round",
    "magazine_size": 8
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "sidearm",
    "loud"
  ],
  "mastery": "vex",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "overwatch"
  ]
}
```

### 15.2 .45 Heavy Pistol

Rules definition:

```text
.45 Heavy Pistol
Martial Ranged Weapon
Damage: 1d12 piercing
Range: 30/90
Magazine: 6
Properties: Ammunition, Magazine 6, Reload, Sidearm, Heavy Sidearm, Loud
Mastery: Slow
Fire Modes: Single Shot, Aimed Shot, Overwatch
```

Heavy Sidearm rule:

```text
Heavy Sidearm.
If your Strength score is lower than 13, attacks with this weapon have Disadvantage unless you are Braced.
```

Suggested data:

```json
{
  "id": "pistol_45_heavy",
  "name": ".45 Heavy Pistol",
  "family": ".45 Pistols",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "1d12",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 30,
    "long_ft": 90
  },
  "ammo": {
    "type": "pistol_45_round",
    "magazine_size": 6
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "sidearm",
    "heavy_sidearm",
    "loud"
  ],
  "requirements": {
    "strength_min_without_disadvantage": 13,
    "braced_ignores_strength_penalty": true
  },
  "mastery": "slow",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "overwatch"
  ]
}
```

### 15.3 .45 Compact Pistol

Rules definition:

```text
.45 Compact Pistol
Martial Ranged Weapon
Damage: 1d8 piercing
Range: 30/90
Magazine: 6
Properties: Ammunition, Magazine 6, Reload, Sidearm, Light, Concealable, Loud
Mastery: Vex
Fire Modes: Single Shot, Aimed Shot, Overwatch
```

Concealable rule:

```text
Concealable.
You have Advantage on Dexterity (Sleight of Hand) checks made to hide this weapon on your person.
```

Suggested data:

```json
{
  "id": "pistol_45_compact",
  "name": ".45 Compact Pistol",
  "family": ".45 Pistols",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "1d8",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 30,
    "long_ft": 90
  },
  "ammo": {
    "type": "pistol_45_round",
    "magazine_size": 6
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "sidearm",
    "light",
    "concealable",
    "loud"
  ],
  "mastery": "vex",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "overwatch"
  ]
}
```

---

## 16. Weapon family: Armalite Rifles

Armalite Rifles are the main tactical firearm family. They should be powerful, but their power should come from range, fire modes, and action economy choices rather than huge damage dice.

### 16.1 Armalite Rifle

General-purpose rifle.

Rules definition:

```text
Armalite Rifle
Martial Ranged Weapon
Damage: 1d12 piercing
Range: 120/360
Magazine: 20
Properties: Ammunition, Magazine 20, Reload, Two-Handed, Burst, Auto, Loud
Mastery: Vex
Fire Modes: Single Shot, Aimed Shot, Controlled Burst, Automatic Sweep, Suppressive Fire, Overwatch
```

Suggested data:

```json
{
  "id": "armalite_rifle_standard",
  "name": "Armalite Rifle",
  "family": "Armalite Rifles",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "1d12",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 120,
    "long_ft": 360
  },
  "ammo": {
    "type": "rifle_round",
    "magazine_size": 20
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "two_handed",
    "burst",
    "auto",
    "loud"
  ],
  "mastery": "vex",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "controlled_burst",
    "automatic_sweep",
    "suppressive_fire",
    "overwatch"
  ]
}
```

### 16.2 Armalite Battle Rifle

Heavier rifle with slightly better base damage but less smooth handling.

Rules definition:

```text
Armalite Battle Rifle
Martial Ranged Weapon
Damage: 2d6 piercing
Range: 150/500
Magazine: 20
Properties: Ammunition, Magazine 20, Reload, Two-Handed, Heavy, Burst, Auto, Loud
Mastery: Slow
Fire Modes: Single Shot, Aimed Shot, Controlled Burst, Automatic Sweep, Suppressive Fire, Overwatch
```

Suggested data:

```json
{
  "id": "armalite_battle_rifle",
  "name": "Armalite Battle Rifle",
  "family": "Armalite Rifles",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "2d6",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 150,
    "long_ft": 500
  },
  "ammo": {
    "type": "rifle_round",
    "magazine_size": 20
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "two_handed",
    "heavy",
    "burst",
    "auto",
    "loud"
  ],
  "mastery": "slow",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "controlled_burst",
    "automatic_sweep",
    "suppressive_fire",
    "overwatch"
  ]
}
```


### 16.3 Armalite Precision Rifle

Long-range rifle. It should not get full-auto modes by default.

Rules definition:

```text
Armalite Precision Rifle
Martial Ranged Weapon
Damage: 2d8 piercing
Range: 200/800
Magazine: 5
Properties: Ammunition, Magazine 5, Reload, Two-Handed, Heavy, Loud, Precision
Mastery: Slow
Fire Modes: Single Shot, Aimed Shot, Overwatch
```

Precision rule:

```text
Precision.
When you use Aimed Shot with this weapon and choose the +1d6 damage option, the bonus damage becomes +2d6 instead.
```

Suggested data:

```json
{
  "id": "armalite_precision_rifle",
  "name": "Armalite Precision Rifle",
  "family": "Armalite Rifles",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "2d8",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 200,
    "long_ft": 800
  },
  "ammo": {
    "type": "rifle_round",
    "magazine_size": 5
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "two_handed",
    "heavy",
    "loud",
    "precision"
  ],
  "mastery": "slow",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "overwatch"
  ]
}
```

### 16.4 Armalite Automatic Rifle

Automatic support rifle. This should be a squad or elite weapon, not the default firearm every enemy carries.

Rules definition:

```text
Armalite Automatic Rifle
Martial Ranged Weapon
Damage: 2d6 piercing
Range: 120/360
Magazine: 30
Properties: Ammunition, Magazine 30, Reload, Two-Handed, Heavy, Auto, Loud, Recoil
Mastery: Push
Fire Modes: Single Shot, Aimed Shot, Automatic Sweep, Suppressive Fire, Overwatch
```

Recoil rule:

```text
Recoil.
If you are not Braced, attacks with this weapon after the first attack on your turn have Disadvantage.
```

Suggested data:

```json
{
  "id": "armalite_automatic_rifle",
  "name": "Armalite Automatic Rifle",
  "family": "Armalite Rifles",
  "category": "martial_ranged",
  "weapon_group": "firearm",
  "damage": {
    "dice": "2d6",
    "type": "piercing",
    "ability_modifier": "dexterity"
  },
  "range": {
    "normal_ft": 120,
    "long_ft": 360
  },
  "ammo": {
    "type": "rifle_round",
    "magazine_size": 30
  },
  "properties": [
    "ammunition",
    "magazine",
    "reload",
    "two_handed",
    "heavy",
    "auto",
    "loud",
    "recoil"
  ],
  "mastery": "push",
  "fire_modes": [
    "single_shot",
    "aimed_shot",
    "automatic_sweep",
    "suppressive_fire",
    "overwatch"
  ]
}
```

---

## 17. Heavy ordnance: SAM-7 Missiles

SAM-7 Missiles should be treated as rare set-piece ordnance, not normal player equipment.

Do not implement real-world missile operation. Keep the game mechanic abstract:

```text
Lock-On → Fire Missile → Save/Damage/Blast → Consume Missile
```

### 17.1 SAM-7 Launcher

Rules definition:

```text
SAM-7 Launcher
Heavy Ordnance
Properties: Two-Handed, Heavy, Loud, Exotic, Lock-On Required
Ammunition: SAM-7 Missile
Normal targeting range: 600 feet
Fire Modes: Lock-On, Fire Missile
```

Suggested data:

```json
{
  "id": "sam7_launcher",
  "name": "SAM-7 Launcher",
  "family": "SAM-7 Missiles",
  "category": "heavy_ordnance",
  "weapon_group": "firearm_ordnance",
  "range": {
    "normal_ft": 600,
    "long_ft": null
  },
  "ammo": {
    "type": "sam7_missile",
    "magazine_size": 1
  },
  "properties": [
    "two_handed",
    "heavy",
    "loud",
    "exotic",
    "lock_on_required",
    "consumable_ammunition"
  ],
  "proficiency": "heavy_ordnance",
  "fire_modes": [
    "sam7_lock_on",
    "sam7_fire_missile"
  ]
}
```

### 17.2 Heavy Ordnance proficiency

Rules text:

```text
Heavy Ordnance.
A creature without Heavy Ordnance proficiency has Disadvantage on checks and attack rolls made to operate this weapon, and targets have Advantage on saving throws against it.
```

Implementation requirements:

- Add proficiency key `heavy_ordnance` if proficiency categories are extensible.
- If proficiency categories are not extensible, add a per-actor feature/tag such as `proficient_heavy_ordnance`.
- The UI should clearly display whether the user is proficient.
- Nonproficiency should not prevent use; it should make use risky.

### 17.3 SAM-7 Lock-On

Rules text:

```text
SAM-7 Lock-On.
As an Action, choose one flying creature, vehicle, construct, siege engine, or Huge-or-larger creature you can see within 600 feet. The target must not have Total Cover.

Make a Dexterity or Intelligence check using your Proficiency Bonus if you are proficient with Heavy Ordnance.

DC = 10 + the target’s Dexterity modifier + any cover bonus.

On a success, the target is Locked until the end of your next turn.
```

Implementation requirements:

- Uses Action.
- Target eligibility should be DM-overridable.
- Target must be visible and within 600 feet unless DM overrides.
- Total Cover prevents Lock-On.
- Actor chooses Dexterity or Intelligence for the check.
- Add proficiency bonus only if proficient with Heavy Ordnance.
- Apply target state `sam7_locked` on success.
- Lock state should reference the source actor and launcher.
- Expires at end of source actor’s next turn.

Suggested target state:

```json
{
  "id": "sam7_locked",
  "name": "SAM-7 Locked",
  "source_actor_id": "actor_uuid",
  "source_item_id": "sam7_launcher_instance_uuid",
  "target_actor_id": "target_uuid",
  "duration": {
    "ends_at": "end_of_source_next_turn"
  },
  "valid_for_fire_mode": "sam7_fire_missile"
}
```

Suggested event log:

```text
A2-Jeeves attempts SAM-7 Lock-On against Adult Blue Dragon.
Check: Intelligence + Proficiency vs DC 13.
Success. Adult Blue Dragon is SAM-7 Locked until end of A2-Jeeves’s next turn.
```

### 17.4 SAM-7 Fire Missile

Rules text:

```text
SAM-7 Fire Missile.
As an Action, fire at a target currently Locked by this launcher. The target makes a Dexterity saving throw.

Save DC = 8 + your Proficiency Bonus + your Dexterity or Intelligence modifier.

On a failed save, the target takes 12d10 fire and force damage and falls 60 feet if it is flying by nonmagical means.
On a successful save, the target takes half damage and does not fall.

Creatures within 20 feet of the target must make the same saving throw, taking 6d10 fire and thunder damage on a failed save, or half as much on a successful one.

The SAM-7 Missile is consumed whether the target succeeds or fails.
```

Implementation requirements:

- Requires a valid `sam7_locked` state from the same source actor and launcher.
- Requires loaded SAM-7 Missile ammo.
- Uses Action.
- Consumes missile on fire.
- Target makes Dexterity save.
- Save DC uses Dex or Int, chosen by operator.
- Primary target damage: 12d10 split or grouped as fire/force.
- Secondary blast: 20-foot radius/circle/sphere depending map support.
- Secondary damage: 6d10 fire/thunder.
- Flying fall rider only applies to nonmagical flight.
- DM should be able to toggle fall rider on/off during resolution.
- Legendary Resistance and normal save-modifying features work.
- The event is Loud.

Suggested fire mode data:

```json
{
  "id": "sam7_fire_missile",
  "name": "SAM-7 Fire Missile",
  "requires_item": "sam7_launcher",
  "requires_ammo": "sam7_missile",
  "requires_target_state": "sam7_locked",
  "action_cost": "action",
  "ammo_cost": 1,
  "resolution": "target_save_plus_blast",
  "save": {
    "ability": "dexterity",
    "dc_formula": "8 + source.proficiency_bonus + chosen_modifier:dexterity_or_intelligence"
  },
  "primary_damage": {
    "dice": "12d10",
    "types": ["fire", "force"],
    "save_success": "half"
  },
  "primary_rider": {
    "condition": "if_target_flying_nonmagically",
    "effect": "fall_60_ft_on_failed_save"
  },
  "blast": {
    "radius_ft": 20,
    "damage": {
      "dice": "6d10",
      "types": ["fire", "thunder"],
      "save_success": "half"
    }
  },
  "consumes_ammo_on_use": true,
  "loud": true
}
```

Acceptance criteria:

- Cannot fire without Lock-On unless DM override is used.
- Cannot fire without a SAM-7 Missile loaded/available.
- Consumes missile on use regardless of hit/save outcome.
- Applies primary and blast damage separately.
- Gives DM an explicit fall-rider toggle.
- Logs the full sequence clearly.

### 17.5 SAM-7 counterplay

Counterplay should be supported narratively first, then automated later.

Rules guidance:

| Counterplay | Mechanical result |
|---|---|
| Total Cover | Lock-On fails or existing Lock-On ends at DM discretion. |
| Invisibility | Lock-On cannot begin unless operator has a way to perceive target. |
| Heavy magical obscurement | Lock-On check has Disadvantage or fails, DM choice. |
| Target lands before missile is fired | Fire still allowed if lock remains, but target may have Advantage on save. |
| Shield/defensive reactions | Apply if relevant under normal table rules. |
| Legendary Resistance | Works normally. |
| Wall of Force or equivalent | Blocks line/effect as Total Cover. |
| Antimagic or magic interference | DM adjudication; usually Advantage on save or Lock-On failure. |

Implementation recommendation:

- v1: expose DM toggles for Advantage/Disadvantage, cover, and valid target.
- v2: automate obvious cases if the map and condition engine can support them.

---

## 18. Balance tuning for level 11

The current campaign target is a level 11 party.

Design benchmark:

```text
Firearms should be stronger than mundane bows in specific tactical contexts, but should not exceed martial melee/ranged optimization by a large margin without spending resources or accepting constraints.
```

Expected on-hit averages with Dex 20:

| Weapon | Damage | Average on hit |
|---|---:|---:|
| .45 Compact Pistol | 1d8 + 5 | 9.5 |
| .45 Service Pistol | 1d10 + 5 | 10.5 |
| .45 Heavy Pistol | 1d12 + 5 | 11.5 |
| Armalite Rifle | 1d12 + 5 | 11.5 |
| Armalite Battle Rifle | 2d6 + 5 | 12 |
| Armalite Precision Rifle | 2d8 + 5 | 14 |
| Armalite Automatic Rifle | 2d6 + 5 | 12 |

Controlled Burst averages:

| Weapon | Controlled Burst hit |
|---|---:|
| Armalite Rifle | 2d12 + 5 = 18 avg |
| Armalite Battle Rifle | 3d6 + 5 = 15.5 avg |

Tuning notes:

- If Armalite Rifles feel weak, improve tactical options before increasing damage.
- If Armalite Rifles feel too strong, reduce magazine size or increase ammo scarcity before reducing damage.
- If Controlled Burst is overused, keep once-per-turn and increase jam risk only for burst/auto modes.
- If Suppressive Fire is too strong, reduce area to 5-foot cube or make save DC use `8 + PB + Dex mod - 2`.
- If Automatic Sweep is too strong, make successful saves take no damage, as currently designed.
- If SAM-7 Missiles trivialize bosses, require Lock-On and Fire Missile on separate turns and increase counterplay.

---

## 19. Cover and targeting rules

Use normal D&D cover as the first-class balancing tool.

| Cover state | Firearm interaction |
|---|---|
| No Cover | Normal attack/save. |
| Half Cover | Normal D&D cover bonus. Aimed Shot can ignore Half Cover. For Automatic Sweep, grants Advantage on save. |
| Three-Quarters Cover | Normal D&D cover bonus. For Automatic Sweep, automatic success. |
| Total Cover | Cannot be targeted or affected unless a specific rule says otherwise. |
| Prone | Normal ranged attack implications. Also counts as Braced for the shooter. |

Implementation requirements:

- Do not add armor penetration in the first implementation.
- Do not make firearms ignore shields by default.
- Do not make firearms ignore natural armor by default.
- Cover should be a DM-visible modifier if not map-derived.
- Aimed Shot should be able to ignore Half Cover.

Potential future enhancement:

```text
Armor Piercing Ammunition
Rare ammunition that ignores Half Cover or reduces nonmagical armor bonus by a small amount.
Do not add this until baseline firearms have been tested.
```

---

## 20. Magic interactions

Default rule:

```text
Magic works normally unless a specific firearm rule says otherwise.
```

Suggested interactions:

| Magic/effect | Interaction |
|---|---|
| Shield | Works against attack rolls. |
| Blur | Works against attack rolls. |
| Mirror Image | Works against attack rolls, not area saves. |
| Invisibility | Blocks or complicates target selection. |
| Fog Cloud/Darkness | Blocks or complicates line of sight. |
| Wall of Force | Total Cover. |
| Absorb Elements | Works against applicable elemental damage from SAM-7 effects if table interpretation allows. |
| Counterspell | Does not counter a mundane firearm. Could counter a magical ammo effect if one exists. |
| Silence | Does not necessarily silence a firearm unless DM wants magical silence to suppress sound events; decide per campaign tone. |

Implementation recommendation:

- Do not build special magic exceptions into the firearm engine early.
- Keep magic interactions as ordinary attack/save/condition/cover logic.
- Add explicit tags only when table play proves it necessary.

---

## 21. Proficiency model

Recommended v1:

```text
Firearms count as Martial Ranged Weapons unless the campaign enables explicit Firearms proficiency.
Heavy Ordnance is separate.
```

This avoids a large character-sheet migration just to make the first version playable.

Recommended v2:

```text
Add proficiency groups:
- firearms
- heavy_ordnance
```

Possible proficiency behavior:

| User proficiency | Effect |
|---|---|
| Not proficient with firearm | No PB to attack rolls; reload/clear jam costs Action. |
| Proficient with firearm | Add PB to attack rolls; reload/clear jam costs Bonus Action. |
| Proficient with Heavy Ordnance | Add PB to SAM-7 Lock-On checks and normal save DC. |
| Not proficient with Heavy Ordnance | Disadvantage on operation checks; targets have Advantage on SAM-7 saves. |

Implementation requirement:

- Do not hardcode proficiency to character names.
- Use actor proficiency data where available.
- If unavailable, expose DM override per action.

---

## 22. Ammunition and inventory

### 22.1 Ammo types

Suggested ammo types:

```json
[
  {
    "id": "pistol_45_round",
    "name": ".45 Round",
    "compatible_families": [".45 Pistols"]
  },
  {
    "id": "rifle_round",
    "name": "Rifle Round",
    "compatible_families": ["Armalite Rifles"]
  },
  {
    "id": "sam7_missile",
    "name": "SAM-7 Missile",
    "compatible_families": ["SAM-7 Missiles"]
  }
]
```

### 22.2 Magazine abstraction

Use abstract ammo counts first.

Do not model detachable magazines as separate inventory objects in v1 unless the existing inventory engine already supports it well.

Recommended v1 reload behavior:

```text
Reload sets ammo_current to ammo_max and subtracts the difference from compatible loose ammunition.
```

Example:

```text
Armalite Rifle ammo_current: 4/20
Actor rifle_round inventory: 80
Reload consumes 16 rifle_round
Armalite Rifle ammo_current: 20/20
Actor rifle_round inventory: 64
```

If inventory is not ready:

```text
Use per-weapon ammo only and let the DM manually adjust reserve ammunition.
```

### 22.3 SAM-7 ammunition

SAM-7 Missiles should be separate discrete ammunition items.

Recommended behavior:

```text
1 SAM-7 Missile = 1 shot.
Firing consumes the missile.
Reloading the launcher should not be treated like a normal Bonus Action reload unless the DM explicitly allows it.
```

Implementation behavior:

- Track loaded/unloaded state.
- Track missile count.
- Firing consumes loaded missile.
- Reloading may be disabled during combat by default.
- DM override available.

---

## 23. UI/UX plan

### 23.1 Weapon panel

For firearms, the actor attack panel should show:

```text
Armalite Rifle
Ammo: 17 / 20
State: Ready
Fire Mode: [Single Shot ▼]

[Attack] [Aim] [Reload] [Brace] [Overwatch]
```

If Jammed:

```text
Armalite Rifle
Ammo: 17 / 20
State: Jammed

[Clear Jam] [Reload disabled or secondary]
```

### 23.2 Fire mode dropdown

Available options should be filtered by weapon properties and ammo.

Example for Armalite Rifle:

```text
Single Shot
Aimed Shot
Controlled Burst
Automatic Sweep
Suppressive Fire
Overwatch
```

Example for .45 Service Pistol:

```text
Single Shot
Aimed Shot
Overwatch
```

Example for SAM-7 Launcher:

```text
SAM-7 Lock-On
SAM-7 Fire Missile
```

### 23.3 Action previews

Before resolving an action, the UI should show a concise preview.

Controlled Burst preview:

```text
Controlled Burst
Ammo cost: 3
Attack: Dex + PB
Hit: 2d12 + Dex piercing
Jam risk: Natural 1
```

Suppressive Fire preview:

```text
Suppressive Fire
Ammo cost: 10
Area: 10-ft cube
Save: Wisdom DC 8 + PB + Dex
Failure: Suppressed until end of target turn
No damage
Jam risk: If all targets succeed
```

SAM-7 Fire Missile preview:

```text
SAM-7 Fire Missile
Requires: SAM-7 Locked target
Ammo cost: 1 SAM-7 Missile
Primary save: Dexterity DC 8 + PB + Dex/Int
Failed save: 12d10 fire/force; possible 60-ft fall if nonmagical flight
Success: Half damage, no fall
Blast: 20-ft radius, 6d10 fire/thunder
```

### 23.4 DM overrides

Required DM override controls:

- Ignore ammo requirement.
- Manually spend ammo.
- Mark target behind cover.
- Grant Advantage/Disadvantage.
- Force or clear Jammed.
- Force or clear Suppressed.
- Allow SAM-7 target eligibility.
- Allow SAM-7 Fire Missile without Lock-On.
- Toggle SAM-7 fall rider.
- Mark target as nonmagical flying.

DM override actions must log clearly.

Example:

```text
DM override: SAM-7 Fire Missile allowed without Lock-On.
Reason: cinematic set-piece.
```

---

## 24. Event log requirements

The firearm system should be highly legible in the combat log.

Every firearm action should log:

1. Actor name.
2. Weapon name.
3. Fire mode.
4. Ammo before and after.
5. Action cost.
6. Attack/save result.
7. Damage/effect result.
8. Loud event if applicable.
9. Jam check result if applicable.

Example Single Shot:

```text
A2-Jeeves fires .45 Service Pistol: Single Shot.
Ammo: 8/8 → 7/8.
Attack 19 hits Goblin Captain.
Damage: 1d10 + 5 piercing.
Vex applied.
Loud event created.
```

Example Controlled Burst:

```text
A2-Jeeves fires Armalite Rifle: Controlled Burst.
Ammo: 20/20 → 17/20.
Attack 23 hits Ogre Veteran.
Damage: 2d12 + 5 piercing.
Jam check: no jam.
Loud event created.
```

Example Suppressive Fire:

```text
Enemy Rifleman uses Armalite Automatic Rifle: Suppressive Fire.
Ammo: 30/30 → 20/30.
Area: 10-ft cube.
Wisdom save DC 16.
Goblin Captain fails and is Suppressed until end of turn.
Knight succeeds.
Jam check: no jam.
Loud event created.
```

Example Jam:

```text
A2-Jeeves fires Armalite Rifle: Controlled Burst.
Ammo: 3/20 → 0/20.
Attack roll: natural 1.
Miss.
Armalite Rifle becomes Jammed.
Loud event created.
```

Example SAM-7:

```text
A2-Jeeves fires SAM-7 Launcher at Adult Blue Dragon.
SAM-7 Missile consumed: 1 → 0.
Adult Blue Dragon Dexterity save DC 17: failed.
Primary damage: 12d10 fire/force.
Flight rider: nonmagical flight marked true; target falls 60 ft.
Blast radius: 20 ft.
Cultist A fails: 6d10 fire/thunder.
Cultist B succeeds: half damage.
Loud event created.
```

---

## 25. Data model plan

The clean target model is four layers:

```text
Weapon Definition
  ↓
Weapon Instance
  ↓
Actor Combat State
  ↓
Action Resolution/Event Log
```

### 25.1 Weapon Definition

Static content.

Contains:

- ID.
- Name.
- Family.
- Category.
- Damage.
- Range.
- Properties.
- Mastery.
- Ammo type.
- Magazine size.
- Fire modes.

### 25.2 Weapon Instance

Runtime/saved inventory object.

Contains:

- Definition ID.
- Current ammo.
- Current weapon states, such as Jammed.
- Optional custom name.
- Optional magic modifiers.

### 25.3 Actor Combat State

Turn/session state.

Contains:

- Action availability.
- Bonus Action availability.
- Reaction availability.
- Turn flags.
- Temporary states, such as Braced and Aimed Shot pending.
- Conditions, such as Suppressed.

### 25.4 Action Resolution/Event Log

Records what happened.

Contains:

- Source actor.
- Source item.
- Fire mode.
- Ammo spend.
- Rolls.
- Saves.
- Damage.
- Conditions.
- Area effects.
- Jam result.
- Noise event.

---

## 26. Engine integration plan

### 26.1 Add firearm properties

Add these properties as data-level tags:

```text
magazine
reload
sidearm
loud
burst
auto
heavy_sidearm
concealable
precision
recoil
lock_on_required
consumable_ammunition
exotic
```

Properties should not all need custom code immediately. Some can be descriptive in v1.

### 26.2 Add fire mode registry

Create a registry of fire modes keyed by ID.

Required IDs:

```text
single_shot
aimed_shot
controlled_burst
automatic_sweep
suppressive_fire
overwash
sam7_lock_on
sam7_fire_missile
```

Each mode should declare:

- Required properties.
- Action cost.
- Ammo cost.
- Resolution type.
- Damage behavior.
- Save behavior.
- Area template behavior.
- Condition behavior.
- Jam risk.
- Special validation.

### 26.3 Add validation layer

Before resolving a mode:

```text
validate actor can act
validate weapon exists
validate weapon is not Jammed
validate weapon supports mode
validate ammo is sufficient
validate action/bonus/reaction availability if tracked
validate target/range/template
validate special requirements such as Lock-On
```

Return clear errors.

Example:

```text
Cannot use Controlled Burst: Armalite Rifle has only 2 ammo; requires 3.
```

### 26.4 Add resolution layer

Resolution types:

```text
attack_roll
attack_modifier
area_save
area_condition
ready_reaction_area
target_check_state
target_save_plus_blast
```

Do not hardcode every firearm action as a unique flow if the engine can support generic resolution types.

### 26.5 Add cleanup hooks

Needed cleanup points:

- End of actor turn.
- Start of source actor next turn.
- End of source actor next turn.
- After next attack roll.
- After weapon action resolution.
- When actor moves.
- When actor drops prone.
- When actor takes specific clear action.

Do not block v1 on all hooks. Use manual cleanup where necessary and document limitations.

---

## 27. Map/template integration

Phase 2 and Phase 3 need map support.

Required templates:

| Template | Used by |
|---|---|
| 15-ft cone | Automatic Sweep |
| 30-ft line | Automatic Sweep, Overwatch option |
| 10-ft cube | Suppressive Fire |
| 20-ft radius | SAM-7 blast |
| Custom lane/doorway | Overwatch |

Implementation approach:

1. If existing map templates exist, reuse them.
2. If templates are partial, support manual target selection as fallback.
3. If no map template support exists, implement fire modes with DM-selected target lists first.

Fallback behavior:

```text
Automatic Sweep: DM manually selects affected targets.
Suppressive Fire: DM manually selects area label and affected targets on turn entry.
Overwatch: DM manually triggers reaction shot.
SAM-7 blast: DM manually selects secondary blast targets.
```

Do not delay Phase 1 for map work.

---

## 28. Content authoring implications

The user’s long-term direction for init-tracker favors robust DM-facing authoring tools over repeatedly prompting AI for content.

Firearms should therefore be implemented as schema-aware content where possible.

Authoring UI should eventually support:

- Create firearm family.
- Add damage dice/type.
- Set range.
- Set magazine size.
- Set ammo type.
- Select properties from constrained list.
- Select fire modes from valid mode list.
- Set mastery property.
- Preview action outputs.
- Validate unsupported combinations.

Examples of validation:

```text
A weapon cannot have Controlled Burst unless it has the Burst property.
A weapon cannot have Automatic Sweep unless it has the Auto property.
A weapon cannot use SAM-7 Fire Missile unless it requires SAM-7 Missile ammunition.
A weapon with Magazine must have magazine_size > 0.
A fire mode ammo cost cannot exceed magazine size unless explicitly allowed.
```

Do not expose raw backend-shaped JSON as the primary authoring flow long-term. JSON import is useful for dev/admin work, but normal DM authoring should be guided and constrained.

---

## 29. Suggested implementation passes for AI agents

These are intentionally small enough to hand to coding agents one pass at a time.

Each pass should end with a report containing:

- Files inspected.
- Files changed.
- Root cause / implementation summary.
- Exact behavior added.
- Tests run.
- Remaining risks.
- Best next pass.

### Pass F1: Discover current item/weapon/action architecture

Goal:

```text
Map the existing init-tracker item, weapon, attack, condition, inventory, map-template, and event-log architecture before changing firearm behavior.
```

Suggested discovery commands:

```bash
find . -maxdepth 3 -type f | sort | sed 's#^./##' | head -300
rg -n "weapon|Weapon|attack|Attack|damage|Damage|condition|Condition|inventory|item|Item|ammo|ammunition|reload|mastery|map|template|cone|line|cube|event log|combat log" .
rg -n "Action|Bonus Action|Reaction|turn_flags|turn state|end turn|start turn" .
rg -n "schema|content|items.json|weapons.json|conditions.json|features.json" .
```

Constraints:

- Do not implement yet.
- Do not refactor.
- Produce a short architecture map and recommended target files for F2.

Acceptance:

- Report identifies where static weapon data lives.
- Report identifies where runtime item state lives, if it exists.
- Report identifies attack resolution path.
- Report identifies condition/effect path.
- Report identifies event log path.
- Report identifies map/template support or confirms absence.

### Pass F2: Add firearm property vocabulary and data schema support

Goal:

```text
Add the firearm-specific tags/properties needed by this plan without changing combat behavior yet.
```

Properties:

```text
magazine
reload
sidearm
loud
burst
auto
heavy_sidearm
concealable
precision
recoil
lock_on_required
consumable_ammunition
exotic
```

Constraints:

- Minimal schema/data additions only.
- Preserve existing weapon behavior.
- Existing content must still load.
- Add validation if a schema validator exists.

Acceptance:

- Firearm properties can be represented in weapon definitions.
- Existing weapons still load.
- Tests or smoke checks pass.

### Pass F3: Add weapon instance ammo state

Goal:

```text
Support per-weapon current ammo and magazine max for firearms.
```

Requirements:

- Add `ammo_current` and `ammo_max` to weapon instance/runtime state.
- Initialize from weapon definition magazine size.
- Persist across turn/session state where current inventory state persists.
- Show ammo in attack UI or debug output.

Constraints:

- Do not implement fire modes yet.
- Do not require full inventory ammo reserve yet.
- DM/manual ammo adjustment is acceptable for v1.

Acceptance:

- Armalite Rifle can show `20/20` ammo.
- .45 Service Pistol can show `8/8` ammo.
- Ammo state is per weapon instance, not global per definition.

### Pass F4: Implement Single Shot ammo spend and Loud events

Goal:

```text
Make firearm Single Shot spend ammo and emit a Loud event while preserving normal attack behavior.
```

Requirements:

- Firearms spend 1 ammo on Single Shot.
- Cannot fire with 0 ammo.
- Loud event is logged for weapons with `loud`.
- Existing non-firearm attacks unchanged.

Constraints:

- Keep attack resolution path as close to current as possible.
- No burst/auto yet.

Acceptance:

- .45 Service Pistol at 8/8 becomes 7/8 after firing.
- Armalite Rifle at 20/20 becomes 19/20 after firing.
- 0/8 pistol cannot fire and gives clear error.
- Event log includes Loud marker.

### Pass F5: Implement Reload and Clear Jam primitive

Goal:

```text
Add reload behavior and generic weapon-state clearing support needed for Jammed.
```

Requirements:

- Reload sets firearm ammo to magazine max.
- Action cost is Bonus Action if proficient, otherwise Action.
- Add weapon state support if not already present.
- Add `jammed` state that blocks firing.
- Add `Clear Jam` action.

Constraints:

- If proficiency detection is not available, add DM/manual choice.
- Do not implement jam risk yet.

Acceptance:

- Reload button/action works.
- Jammed weapon cannot fire.
- Clear Jam removes Jammed.
- Event log shows reload and clear jam actions.

### Pass F6: Implement Aimed Shot

Goal:

```text
Add Bonus Action Aimed Shot pending state and apply it to the next Single Shot.
```

Requirements:

- Aim creates pending state.
- User chooses one benefit: ignore Half Cover, ignore long-range Disadvantage, or +1d6 damage.
- Next Single Shot consumes state.
- End of turn clears state.
- Movement clearing can be manual if automatic movement hooks are not ready.

Constraints:

- Do not implement Precision upgrade yet unless trivial.
- Do not refactor cover system broadly.

Acceptance:

- +1d6 damage applies once on hit.
- The pending state is visible.
- The state clears after use or end of turn.

### Pass F7: Implement Controlled Burst and Jam Risk

Goal:

```text
Add Controlled Burst for Burst weapons and implement initial jam-risk handling.
```

Requirements:

- Requires `burst` property.
- Costs 3 ammo.
- Adds one extra weapon damage die on hit.
- Once per turn.
- Natural 1 causes Jammed after resolution.

Constraints:

- Do not implement auto modes in this pass.
- Avoid hardcoding Armalite-only behavior; property-driven.

Acceptance:

- Armalite Rifle can use Controlled Burst.
- .45 Service Pistol cannot.
- Ammo decreases by 3.
- Damage die is derived from weapon base damage.
- Once-per-turn limit works.
- Natural 1 jams weapon.

### Pass F8: Add .45 Pistols and Armalite Rifles content

Goal:

```text
Add the initial firearm content definitions.
```

Weapons:

- .45 Service Pistol.
- .45 Heavy Pistol.
- .45 Compact Pistol.
- Armalite Rifle.
- Armalite Battle Rifle.
- Armalite Precision Rifle.
- Armalite Automatic Rifle.

Constraints:

- Data only if engine support is ready.
- Validate damage type spelling and schema compatibility.
- Keep names exactly as specified.

Acceptance:

- All seven weapons appear in content browser/selection.
- Ammo/magazine values are correct.
- Fire mode availability is correct per weapon.

### Pass F9: Implement Braced and Recoil/Heavy Sidearm support

Goal:

```text
Add Braced state and use it for Heavy Sidearm/Recoil penalties.
```

Requirements:

- Add manual Brace action.
- Braced lasts until start of next turn.
- Heavy Sidearm penalty checks Strength < 13 unless Braced.
- Recoil imposes Disadvantage on attacks after first if not Braced.

Constraints:

- Automatic movement/prone/cover bracing can be follow-up.
- Keep manual Brace reliable.

Acceptance:

- Brace button creates state.
- State expires correctly.
- .45 Heavy Pistol penalty works.
- Armalite Automatic Rifle Recoil works.

### Pass F10: Implement Suppressed condition

Goal:

```text
Add Suppressed actor condition independent of Suppressive Fire.
```

Requirements:

- Disadvantage on next attack roll.
- Speed -10 ft.
- Ends at end of actor turn by default.
- Manual clear actions: drop prone, move behind cover, use action to steady.

Constraints:

- If speed display is not integrated, show condition text clearly.
- If next-attack hook is hard, implement visible/manual consumed marker first.

Acceptance:

- Suppressed can be applied manually.
- Attack disadvantage is applied or clearly prompted.
- Speed penalty is visible.
- End-of-turn cleanup works.

### Pass F11: Implement Automatic Sweep

Goal:

```text
Add Automatic Sweep area-save fire mode for Auto weapons.
```

Requirements:

- Requires `auto`.
- Costs 10 ammo.
- Uses Action.
- Template: 15-ft cone or 30-ft line.
- Dex save DC = 8 + PB + Dex mod.
- Failed save: weapon base damage, no Dex modifier.
- Success: no damage.
- Cover interactions if cover support exists.
- Jam if all targets succeed.

Constraints:

- If map templates are not ready, support DM-selected target list.
- Do not implement Suppressive Fire in same pass unless very small.

Acceptance:

- Armalite Rifle can use Automatic Sweep.
- .45 Pistols cannot.
- Ammo spends 10.
- Saves and damage resolve.
- All-success jam path works.

### Pass F12: Implement Suppressive Fire

Goal:

```text
Add Suppressive Fire area-control fire mode for Auto weapons.
```

Requirements:

- Requires `auto`.
- Costs 10 ammo.
- Uses Action.
- Creates 10-ft cube area until start of source next turn.
- Wisdom save DC = 8 + PB + Dex mod.
- Failure applies Suppressed until end of target turn.
- No damage.
- Frightened immunity grants Advantage.
- Total Cover unaffected.
- Jam if all targets succeed when immediately resolved, or if the DM marks no effect.

Constraints:

- If movement triggers are not ready, support manual target triggering.

Acceptance:

- Area effect is visible or represented in combat state.
- Targets can be resolved manually or automatically.
- Suppressed applies correctly.
- Area expires correctly.

### Pass F13: Implement Overwatch

Goal:

```text
Add firearm Overwatch as a reaction-ready area/lane.
```

Requirements:

- Uses Action to set.
- Creates a pending Overwatch state.
- Allows one Reaction Single Shot when triggered.
- Expires at start of source next turn.
- Manual trigger acceptable for v1.

Constraints:

- Do not build complex movement interception if map event hooks are not ready.

Acceptance:

- Overwatch can be set.
- Pending state visible.
- Reaction shot can be triggered.
- Ammo spends only on shot.
- State clears after shot or expiration.

### Pass F14: Implement SAM-7 Lock-On

Goal:

```text
Add SAM-7 Launcher content and Lock-On action.
```

Requirements:

- Add SAM-7 Launcher and SAM-7 Missile content.
- Add Heavy Ordnance proficiency handling or DM override.
- Lock-On uses Action.
- Target must be visible/eligible unless DM override.
- Check uses Dex or Int.
- Success applies SAM-7 Locked state.
- Lock expires at end of source next turn.

Constraints:

- Do not implement Fire Missile yet if Lock-On state is not stable.

Acceptance:

- SAM-7 Launcher appears in content.
- SAM-7 Lock-On action works.
- Locked state appears on target.
- Expiration works.

### Pass F15: Implement SAM-7 Fire Missile

Goal:

```text
Add SAM-7 Fire Missile resolution.
```

Requirements:

- Requires SAM-7 Locked target.
- Requires SAM-7 Missile ammo.
- Uses Action.
- Consumes missile.
- Target Dex save.
- Failed save: 12d10 fire/force.
- Successful save: half damage.
- Secondary 20-ft blast: 6d10 fire/thunder, save for half.
- Optional nonmagical flight fall rider.
- Loud event.

Constraints:

- Use manual secondary target selection if map blast support is incomplete.
- DM fall toggle required.

Acceptance:

- Cannot fire without lock unless DM override.
- Missile consumed on use.
- Primary and blast damage resolve.
- Fall rider can be toggled.
- Event log is complete.

### Pass F16: Add DM-facing firearm content authoring validation

Goal:

```text
Make firearm content maintainable from the DM/admin UI rather than only JSON/code.
```

Requirements:

- Guided fields for damage, range, magazine, ammo type, properties, fire modes, mastery.
- Validate fire mode/property compatibility.
- Preview generated attack text.
- Avoid raw freeform backend-shaped fields as the main UI.

Constraints:

- This is lower priority than a working combat implementation.
- Do not overbuild before field testing.

Acceptance:

- DM can create a new firearm safely.
- Invalid combinations are blocked or warned.
- Created firearm works in combat.

---

## 30. Testing plan

### 30.1 Unit-level tests

Test cases:

```text
Single Shot spends 1 ammo.
Single Shot fails at 0 ammo.
Reload restores ammo.
Jammed blocks firing.
Clear Jam removes Jammed.
Controlled Burst spends 3 ammo.
Controlled Burst adds one weapon die.
Controlled Burst once-per-turn limit works.
Aimed Shot +1d6 applies once.
Suppressed applies next-attack disadvantage.
Suppressed applies speed penalty.
Automatic Sweep save damage excludes Dex modifier.
Suppressive Fire applies Suppressed and no damage.
SAM-7 Lock-On applies locked state.
SAM-7 Fire Missile requires locked state.
SAM-7 Fire Missile consumes missile.
```

### 30.2 UI smoke tests

Manual tests:

1. Add .45 Service Pistol to character.
2. Confirm ammo shows 8/8.
3. Fire once.
4. Confirm ammo 7/8 and Loud log.
5. Reload.
6. Confirm ammo 8/8.
7. Add Armalite Rifle.
8. Confirm Controlled Burst appears.
9. Use Controlled Burst.
10. Confirm ammo 17/20 and extra die.
11. Force Jammed.
12. Confirm weapon cannot fire.
13. Clear Jam.
14. Confirm weapon can fire again.
15. Add Suppressed manually to target.
16. Confirm next attack has disadvantage or prompt.
17. Add SAM-7 Launcher.
18. Lock target.
19. Fire missile.
20. Confirm missile consumed and damage resolved.

### 30.3 Encounter tests

Run these table-style tests:

#### Test A: Basic pistol fight

Actors:

- 1 PC with .45 Service Pistol.
- 3 low-AC enemies.

Expected:

- Pistol feels strong but not encounter-breaking.
- Ammo/reload visible but not annoying.
- Sidearm matters in close quarters.

#### Test B: Armalite Rifle skirmish

Actors:

- 1 PC with Armalite Rifle.
- 4 enemies using cover.

Expected:

- Single Shot and Controlled Burst feel distinct.
- Aimed Shot matters against Half Cover.
- Ammo pressure appears after multiple bursts.

#### Test C: Suppressive Fire corridor

Actors:

- 1 NPC with Armalite Automatic Rifle.
- 3 PCs crossing a hallway.

Expected:

- Suppression changes movement decisions.
- It does not hard-lock the party.
- Dropping prone/using cover feels useful.

#### Test D: SAM-7 boss set-piece

Actors:

- 1 SAM-7 operator.
- 1 flying Huge target.
- Several nearby secondary targets.

Expected:

- Lock-On creates warning window.
- Fire Missile feels dramatic.
- Boss is hurt, not necessarily deleted.
- Counterplay is clear.

---

## 31. Tuning knobs

If the subsystem feels off, tune these in order.

### Firearms too strong

1. Reduce ammo availability.
2. Increase reload friction.
3. Make cover more common.
4. Limit Controlled Burst to once per turn, if not already enforced.
5. Reduce Automatic Sweep damage to one die only for multi-die weapons.
6. Lower magazine sizes.
7. Increase Jam Risk only for burst/auto modes.
8. Reduce range last.
9. Reduce damage dice only if all else fails.

### Firearms too weak

1. Make cover interactions clearer.
2. Make Aimed Shot more useful.
3. Let Aimed Shot ignore Three-Quarters Cover at higher rarity, if needed.
4. Increase ammo availability.
5. Increase magazine sizes.
6. Let Controlled Burst add +1d6 flat instead of one weapon die for low-die weapons.
7. Add rare ammo later.

### Suppressive Fire too strong

1. Reduce area to 5-foot cube.
2. Make save DC `8 + PB + Dex mod - 2`.
3. Let Frightened immunity auto-succeed.
4. Let cover grant automatic success more often.
5. Require Braced for Suppressive Fire.

### Suppressive Fire too weak

1. Increase area to 15-foot cube.
2. Let failure also prevent Reactions until end of turn.
3. Let failure reduce speed by half instead of -10 ft.
4. Let entering the area trigger immediately and starting turn trigger separately.

Only apply one tuning change at a time.

---

## 32. Known non-goals for first implementation

Do not implement these in the first firearm pass:

- Armor penetration.
- Hit locations.
- Bleeding/wound subsystem.
- Detailed recoil simulation.
- Real-world caliber modeling.
- Real-world SAM-7 operation.
- Complex suppressor/sound propagation.
- Per-bullet trajectories.
- Detachable magazine inventory objects unless already easy.
- Real-world firearm customization tree.
- Ballistic tables.
- Separate initiative rules for firearms.
- Called-shot instant kill mechanics.

These can be considered later only if table play proves they are needed.

---

## 33. Safety and content boundary for future agents

This project is for fantasy tabletop gameplay and local software implementation.

Agents must avoid:

- Real-world weapon construction details.
- Real-world explosive or missile handling details.
- Real-world tactical instructions.
- Real-world procurement guidance.
- Real-world optimization of lethality.

Agents may include:

- Abstract D&D damage dice.
- Abstract range numbers for gameplay.
- Ammo counters.
- Conditions.
- Saving throws.
- Map templates.
- Fictionalized event logs.
- DM adjudication notes.

---

## 34. Open questions

These should be answered after repo inspection or table testing.

1. Does init-tracker currently support per-item runtime state?
2. Does init-tracker currently persist ammo-like counters?
3. Does action economy tracking exist and block actions, or is it advisory only?
4. Does the map engine support cones, lines, cubes, and radii?
5. Do map movement events exist for Overwatch/Suppressive Fire triggers?
6. Does the condition engine support “next attack only” disadvantage?
7. Does the condition engine support speed modifiers?
8. Does the weapon engine support Weapon Mastery as data?
9. Does the content authoring UI currently support custom weapon properties?
10. How should firearm proficiency be represented in the current character model?
11. Should SAM-7 Missiles be hidden from normal player inventory screens by default?
12. Should Loud events affect stealth automatically or remain log-only?
13. Should Silence suppress Loud events in this campaign?
14. Should magical ammunition be allowed later?
15. Should firearms be legal, black-market, faction-locked, or artifact-level in the setting?

---

## 35. Recommended first coding prompt

Use this as the first agent prompt when starting implementation.

```text
We are adding a D&D 2024-compatible firearm subsystem to init-tracker using living_firearm_plans.md as the source plan.

First pass only: inspect the current repo architecture and report where firearm support should attach. Do not implement behavior yet.

Focus areas:
- static item/weapon definitions
- runtime item/inventory state
- attack resolution
- damage resolution
- conditions/effects
- action/bonus/reaction tracking
- turn start/end cleanup hooks
- tactical map templates/area effects
- event/combat log
- content authoring/admin UI

Start with:
find . -maxdepth 3 -type f | sort | sed 's#^./##' | head -300
rg -n "weapon|Weapon|attack|Attack|damage|Damage|condition|Condition|inventory|item|Item|ammo|ammunition|reload|mastery|map|template|cone|line|cube|event log|combat log" .
rg -n "Action|Bonus Action|Reaction|turn_flags|turn state|end turn|start turn" .
rg -n "schema|content|items.json|weapons.json|conditions.json|features.json" .

Report:
- files inspected
- relevant architecture found
- where weapon definitions live
- whether per-item runtime state exists
- where attacks and damage resolve
- where conditions/effects live
- where map templates/area effects live, if any
- where event log output happens
- recommended files for the next pass
- risks/unknowns
- best next implementation pass

Constraints:
- no refactor
- no behavior changes
- no broad cleanup
- do not add real-world firearm details
```

---

## 36. Recommended initial content set

Implement in this order:

1. .45 Service Pistol
2. Armalite Rifle
3. Armalite Battle Rifle
4. .45 Heavy Pistol
5. .45 Compact Pistol
6. Armalite Precision Rifle
7. Armalite Automatic Rifle
8. SAM-7 Launcher
9. SAM-7 Missile

Reason:

- .45 Service Pistol tests basic sidearm/ammo/reload behavior.
- Armalite Rifle tests main rifle behavior and burst/auto availability.
- Armalite Battle Rifle tests multi-die damage and Slow mastery.
- Heavy/Compact pistols test property variants.
- Precision Rifle tests Aimed Shot/Precision.
- Automatic Rifle tests Recoil and suppression-heavy play.
- SAM-7 should wait until base state/action/ammo patterns are stable.

---

## 37. Table-facing final rules summary

This is the concise version to show players once implementation exists.

```text
Firearms use magazines and must be reloaded.

Single Shot spends 1 ammo and works like a normal ranged weapon attack.

Aimed Shot uses a Bonus Action and improves your next Single Shot this turn.

Controlled Burst spends 3 ammo, adds one extra weapon die on hit, and can be used once per turn.

Automatic Sweep spends 10 ammo and forces Dex saves in a cone or line.

Suppressive Fire spends 10 ammo and creates a temporary suppressed area.

Suppressed creatures have Disadvantage on their next attack and -10 ft speed until the end of their turn.

Burst and automatic fire can Jam. A Jammed weapon cannot fire until cleared.

SAM-7 Missiles require Lock-On, consume rare missile ammunition, and are treated as heavy ordnance set-piece weapons.
```

---

---

## 38. Vandergraff “Black and Tans” enemy package

This package treats the **Vandergraff Black and Tans** as a fictional occupying paramilitary force: disciplined, brutal, well-equipped, and tactically modern by D&D standards, but not superhuman. They should feel scary because they use **cover, suppression, radios, checkpoints, searchlights, and coordinated squads**, not because they cheat the game.

For a party of **10 level-11 PCs**, D&D 2024’s XP budget gives this rough target:

| Difficulty | XP per level-11 PC | Party budget for 10 PCs |
| ---------- | -----------------: | ----------------------: |
| Low        |              1,900 |                  19,000 |
| Moderate   |              2,900 |                  29,000 |
| High       |              4,100 |                  41,000 |

For this specific campaign, I would usually target **30,000–36,000 XP** for a serious set-piece fight. That is above Moderate, below High, and safer for a large table than a full hard-budget gunfight. D&D 2024’s own encounter rules say High encounters can be lethal and require smart tactics/luck, and they also warn that many enemies can spike harder than expected. ([Roll20][1])

---

### Design assumptions

Use the firearm rules from `living_firearm_plans.md`, especially:

```text
Magazine
Reload
Loud
Sidearm
Aimed Shot
Controlled Burst
Suppressive Fire
Jammed
Braced
```

Official D&D 2024 already includes a pistol and musket baseline: the **Pistol** is 1d10 piercing, range 30/90, Ammunition, Loading, Vex; the **Musket** is 1d12 piercing, range 40/120, Ammunition, Loading, Two-Handed, Slow. The homebrew here replaces the old single-shot feel with magazine and fire-mode play. ([D&D Beyond][2])

For loot, D&D 2024 explicitly gives the DM control over whether monster equipment is recoverable and notes that monsters are proficient with gear in their stat block. That supports “some guns drop usable, some are damaged, some are locked/serialized, some need repair.” ([Roll20][3])

---

### Encounter philosophy

#### Do not make this a firing squad

The Black and Tans should use modern-ish tactics, but the encounter should still be D&D:

* Give the party **multiple cover routes**.
* Do not start all enemies with clean line of sight.
* Avoid putting all enemies on overwatch before initiative.
* Do not open with SAM-7 fire against clustered PCs.
* Use reloads and jams visibly.
* Let players disrupt radio coordination, lights, doors, ammo crates, officers, and medics.
* Let morale break when leadership drops.

The fight should feel like:

```text
A hard tactical raid against a violent occupying force.
Not: “The DM brought guns, so everyone dies.”
```

---

### Shared Black and Tan traits

Use these on most Vandergraff Black and Tan enemies.

#### Vandergraff Drill

```text
Vandergraff Drill.
If this creature starts its turn within 30 feet of an allied Black and Tan officer it can see or hear, it gains +1 to attack rolls until the start of its next turn.
```

Use this sparingly. It makes officers matter without making every mook elite.

#### Baton and Boot

```text
Baton and Boot.
This creature has Advantage on attack rolls against a Prone creature within 5 feet of it.
```

Good theme, nasty but not broken.

#### Fire Discipline

```text
Fire Discipline.
This creature does not expend extra ammunition on a missed attack unless it used Controlled Burst, Automatic Sweep, or Suppressive Fire.
```

Mostly an init-tracker bookkeeping note.

#### Morale: Chain of Command

```text
Chain of Command.
When the highest-ranking visible Black and Tan officer is reduced to 0 HP, each lower-ranking Black and Tan that can see it must make a DC 13 Wisdom saving throw at the start of its next turn.

On a failure, it either retreats to cover, spends its Action regrouping, or attempts to flee if already Bloodied.
```

This keeps the fight fair for a 10-player table. The party should be rewarded for decapitation tactics.

---

### Enemy roster

The following are custom D&D 2024-style humanoids. The CRs are practical table estimates, using D&D’s CR-to-XP table as the encounter-budget interface. CR 3 is 700 XP, CR 4 is 1,100 XP, CR 5 is 1,800 XP, CR 6 is 2,300 XP, CR 7 is 2,900 XP, CR 8 is 3,900 XP, and CR 9 is 5,000 XP. ([D&D Beyond][4])

---

#### Weak enemy: Black and Tan Constable

**Role:** weak pistol trooper / checkpoint thug
**CR:** 3, 700 XP
**Use count:** 2–6 in a large fight

```text
Black and Tan Constable
Medium Humanoid, typically Lawful Evil
CR 3, XP 700, PB +2

AC 16
HP 52
Speed 30 ft.

STR 14 (+2), DEX 16 (+3), CON 14 (+2), INT 10 (+0), WIS 11 (+0), CHA 11 (+0)

Saving Throws Dex +5, Con +4
Skills Athletics +4, Intimidation +2, Perception +2
Senses Passive Perception 12
Languages Common plus one Vandergraff regional language

Gear:
- .45 Pistol, 2 loaded magazines
- Baton
- Flak coat
- Manacles
- Checkpoint pass papers
```

##### Actions

```text
Multiattack.
The Constable makes two attacks, using .45 Pistol or Baton in any combination.

.45 Pistol.
Ranged Weapon Attack: +5 to hit, range 40/120 ft., one target.
Hit: 8 (1d10 + 3) piercing damage.

Baton.
Melee Weapon Attack: +4 to hit, reach 5 ft., one target.
Hit: 6 (1d8 + 2) bludgeoning damage.
If the target is Prone, the target takes an extra 3 bludgeoning damage.

Rough Arrest.
Melee Weapon Attack: +4 to hit, reach 5 ft., one Medium or smaller creature.
Hit: 5 bludgeoning damage, and the target must succeed on a DC 12 Strength saving throw or be Grappled until the end of the Constable’s next turn.
```

##### Bonus Actions

```text
Brace.
The Constable gains the Braced condition until the start of its next turn.

Reload.
The Constable reloads its .45 Pistol.
```

##### Loot

Recoverable:

* 50% chance: usable **.45 Pistol**
* 1d2 loaded .45 magazines
* Baton
* Manacles
* 2d10 gp equivalent in pay scrip, bribes, jewelry, or confiscated coins
* Patrol papers that can grant Advantage on one Deception check at a checkpoint

DM note: Constables are the disposable front line. They should not be individually scary to level-11 PCs, but six of them using pistols from cover can still create pressure.

---

#### Weak-mid enemy: Black and Tan Rifleman

**Role:** standard Armalite user
**CR:** 4, 1,100 XP
**Use count:** 3–6 in a large fight

```text
Black and Tan Rifleman
Medium Humanoid, typically Lawful Evil
CR 4, XP 1,100, PB +2

AC 16
HP 68
Speed 30 ft.

STR 13 (+1), DEX 18 (+4), CON 14 (+2), INT 11 (+0), WIS 12 (+1), CHA 10 (+0)

Saving Throws Dex +6, Wis +3
Skills Perception +3, Stealth +6
Senses Passive Perception 13
Languages Common plus one Vandergraff regional language

Gear:
- Armalite Rifle, 3 loaded magazines
- .45 Pistol, 1 loaded magazine
- Knife
- Flak coat
- Field radio earpiece or signal whistle
```

##### Actions

```text
Multiattack.
The Rifleman makes two Armalite Rifle attacks.

Armalite Rifle.
Ranged Weapon Attack: +6 to hit, range 120/360 ft., one target.
Hit: 10 (1d12 + 4) piercing damage.

Controlled Burst.
Before making one Armalite Rifle attack, the Rifleman spends 3 ammo.
On a hit, the attack deals 16 (2d12 + 4) piercing damage.
The Rifleman can use Controlled Burst once per turn.

.45 Pistol.
Ranged Weapon Attack: +6 to hit, range 40/120 ft., one target.
Hit: 9 (1d10 + 4) piercing damage.

Knife.
Melee or Ranged Weapon Attack: +6 to hit, reach 5 ft. or range 20/60 ft., one target.
Hit: 6 (1d4 + 4) piercing damage.
```

##### Bonus Actions

```text
Brace.
The Rifleman gains the Braced condition until the start of its next turn.

Reload.
The Rifleman reloads one firearm.

Move to Firing Position.
If the Rifleman is within 10 feet of Half Cover or better, it moves up to 10 feet without provoking Opportunity Attacks. It must end this movement behind cover.
```

##### Loot

Recoverable:

* 40% chance: usable **Armalite Rifle**
* Otherwise: damaged Armalite Rifle, repairable with tools and parts
* 1d3 loaded rifle magazines
* 1 loaded .45 magazine
* Flak coat, usually damaged
* 1d4 × 10 gp equivalent in military pay, confiscated coin, or black-market script
* Patrol radio token / coded paper scrap

DM note: Riflemen are the baseline. If they are all using Controlled Burst every turn, they become swingy. Use Controlled Burst from 1–2 riflemen per round, not every rifleman.

---

#### Mid enemy: Black and Tan Shield Trooper

**Role:** cover carrier / doorway holder / anti-melee brute
**CR:** 5, 1,800 XP
**Use count:** 1–3 in a large fight

```text
Black and Tan Shield Trooper
Medium Humanoid, typically Lawful Evil
CR 5, XP 1,800, PB +3

AC 19
HP 88
Speed 25 ft.

STR 18 (+4), DEX 14 (+2), CON 16 (+3), INT 10 (+0), WIS 12 (+1), CHA 11 (+0)

Saving Throws Str +7, Con +6, Wis +4
Skills Athletics +7, Intimidation +3, Perception +4
Senses Passive Perception 14
Languages Common plus one Vandergraff regional language

Gear:
- Ballistic shield
- .45 Pistol, 3 loaded magazines
- Baton
- Flak armor
- Door breaching tools
```

##### Traits

```text
Shield Wall.
The Shield Trooper counts as Half Cover for one allied creature directly behind it.

Heavy Shield.
The Shield Trooper has Disadvantage on Dexterity (Stealth) checks.
```

##### Actions

```text
Multiattack.
The Shield Trooper makes two attacks, using .45 Pistol, Baton, or Shield Bash in any combination.

.45 Pistol.
Ranged Weapon Attack: +5 to hit, range 40/120 ft., one target.
Hit: 8 (1d10 + 2) piercing damage.

Baton.
Melee Weapon Attack: +7 to hit, reach 5 ft., one target.
Hit: 8 (1d8 + 4) bludgeoning damage.

Shield Bash.
Melee Weapon Attack: +7 to hit, reach 5 ft., one target.
Hit: 7 (1d6 + 4) bludgeoning damage, and the target must succeed on a DC 15 Strength saving throw or be pushed 10 feet or knocked Prone.
```

##### Reactions

```text
Interpose Shield.
When an allied Black and Tan within 5 feet is hit by an attack, the Shield Trooper can reduce the damage by 10 if the attack came from a direction the shield could plausibly block.
```

##### Loot

Recoverable:

* Ballistic shield, heavy but usable
* .45 Pistol
* 1d3 loaded .45 magazines
* Baton
* Breaching tools
* 2d10 gp equivalent
* 25% chance: officer key ring

##### Ballistic shield player-facing loot rule

```text
Ballistic Shield.
Shield, requires Strength 13.
While wielding this shield, you gain the normal +2 AC bonus from a shield.
As a Bonus Action, choose one direction. Until the start of your next turn, ranged attacks from that direction treat you as having Half Cover.
You have Disadvantage on Dexterity (Stealth) checks while wielding it.
```

This is good loot because it is useful but not campaign-breaking.

---

#### Mid enemy: Black and Tan Suppression Gunner

**Role:** area denial / makes cover matter
**CR:** 6, 2,300 XP
**Use count:** 1–2 normally, 3 only in a major set-piece

```text
Black and Tan Suppression Gunner
Medium Humanoid, typically Lawful Evil
CR 6, XP 2,300, PB +3

AC 16
HP 105
Speed 25 ft.

STR 16 (+3), DEX 16 (+3), CON 18 (+4), INT 10 (+0), WIS 13 (+1), CHA 9 (-1)

Saving Throws Dex +6, Con +7, Wis +4
Skills Athletics +6, Perception +4
Senses Passive Perception 14
Languages Common plus one Vandergraff regional language

Gear:
- Armalite squad automatic configuration, 3 loaded box magazines
- .45 Pistol, 1 loaded magazine
- Flak armor
- Ammunition satchel
```

##### Traits

```text
Set Up Gun.
If the Gunner is Braced, it ignores the Recoil property of its Armalite weapon.

Loudest Thing in the Room.
After the Gunner uses Suppressive Fire or Automatic Sweep, creatures have Advantage on Wisdom (Perception) checks to locate the Gunner until the start of its next turn.
```

##### Actions

```text
Multiattack.
The Gunner makes two Armalite attacks.

Armalite Rifle.
Ranged Weapon Attack: +6 to hit, range 120/360 ft., one target.
Hit: 10 (2d6 + 3) piercing damage.

Controlled Burst.
Before making one Armalite attack, the Gunner spends 3 ammo.
On a hit, the attack deals 13 (3d6 + 3) piercing damage.
The Gunner can use Controlled Burst once per turn.

Suppressive Fire.
The Gunner spends 10 ammo and chooses a 10-foot cube within 120 feet.
Until the start of the Gunner’s next turn, hostile creatures that start their turn in the cube or enter it must make a DC 14 Wisdom saving throw.
On a failed save, the creature is Suppressed until the end of its turn.

Automatic Sweep.
The Gunner spends 10 ammo and chooses a 15-foot cone or 30-foot line within 120 feet.
Each creature in the area makes a DC 14 Dexterity saving throw.
On a failed save, a creature takes 10 (2d6 + 3) piercing damage.
On a successful save, it takes no damage.
```

##### Bonus Actions

```text
Brace.
The Gunner gains the Braced condition until the start of its next turn.

Reload.
The Gunner reloads its Armalite weapon.
```

##### Loot

Recoverable:

* 25% chance: usable Armalite squad automatic configuration
* Otherwise: damaged heavy Armalite parts worth 500–1,000 gp to the right buyer
* 1d2 loaded box magazines
* Ammunition satchel
* Flak armor, damaged
* Field maintenance kit

DM note: This is your “the party respects the battlefield now” enemy. Use suppression to move players, not to stunlock them.

---

#### Mid support enemy: Black and Tan Field Medic

**Role:** keeps officers alive / gives the party a priority target
**CR:** 5, 1,800 XP
**Use count:** 1 per major fight

```text
Black and Tan Field Medic
Medium Humanoid, usually Lawful Evil or Lawful Neutral
CR 5, XP 1,800, PB +3

AC 15
HP 78
Speed 30 ft.

STR 10 (+0), DEX 16 (+3), CON 14 (+2), INT 16 (+3), WIS 16 (+3), CHA 12 (+1)

Saving Throws Dex +6, Int +6, Wis +6
Skills Medicine +9, Perception +6, Investigation +6
Senses Passive Perception 16
Languages Common plus one Vandergraff regional language

Gear:
- .45 Pistol, 2 loaded magazines
- Field medical kit
- Smoke canister x2
- Stimulant ampoule x3
- Officer casualty tags
```

##### Actions

```text
Multiattack.
The Medic makes two .45 Pistol attacks, or makes one .45 Pistol attack and uses Field Treatment.

.45 Pistol.
Ranged Weapon Attack: +6 to hit, range 40/120 ft., one target.
Hit: 9 (1d10 + 3) piercing damage.

Field Treatment.
One allied Black and Tan within 5 feet regains 14 (2d8 + 5) HP.
A creature can benefit from this action only once per encounter.

Smoke Canister.
The Medic throws a smoke canister to a point within 30 feet.
A 10-foot-radius area becomes Heavily Obscured until the end of the Medic’s next turn.
Wind, strong forced movement, or similar magic can disperse the smoke early.
```

##### Bonus Actions

```text
Stimulant Ampoule.
One allied Black and Tan within 5 feet gains 10 temporary HP and can move up to half its Speed without provoking Opportunity Attacks.
```

##### Reactions

```text
Keep the Officer Breathing.
When an allied Black and Tan officer within 5 feet would drop to 0 HP, the Medic can cause that ally to drop to 1 HP instead.
```

##### Loot

Recoverable:

* .45 Pistol
* 1d2 .45 magazines
* 1d2 smoke canisters
* 1d3 field treatment charges
* Medical kit worth 250 gp
* Officer casualty records, potentially useful evidence

##### Player-facing field treatment item

```text
Field Treatment Charge.
As an Action, expend one charge to let a creature within 5 feet spend one Hit Die and regain additional HP equal to your Wisdom or Intelligence modifier.
A creature can benefit from only one Field Treatment Charge per Short Rest.
```

This is useful without replacing magical healing.

---

#### Strong mid enemy: Black and Tan Lieutenant

**Role:** squad commander / morale anchor
**CR:** 7, 2,900 XP
**Use count:** 1–2 in a large fight

```text
Black and Tan Lieutenant
Medium Humanoid, typically Lawful Evil
CR 7, XP 2,900, PB +3

AC 17
HP 118
Speed 30 ft.

STR 14 (+2), DEX 18 (+4), CON 16 (+3), INT 14 (+2), WIS 14 (+2), CHA 16 (+3)

Saving Throws Dex +7, Con +6, Wis +5, Cha +6
Skills Intimidation +6, Perception +5, Persuasion +6
Senses Passive Perception 15
Languages Common plus two Vandergraff regional languages

Gear:
- Armalite Rifle, 3 loaded magazines
- .45 Pistol, 2 loaded magazines
- Officer saber
- Flak-lined officer coat
- Command whistle
- Coded orders
```

##### Traits

```text
Command Presence.
Allied Black and Tans within 30 feet who can see or hear the Lieutenant gain +1 to Wisdom saving throws and morale checks.

Officer Priority.
If the Lieutenant is Bloodied, one allied Black and Tan within 30 feet can use its Reaction to move up to half its Speed toward cover.
```

##### Actions

```text
Multiattack.
The Lieutenant makes three attacks, using Armalite Rifle, .45 Pistol, or Officer Saber in any combination.

Armalite Rifle.
Ranged Weapon Attack: +7 to hit, range 120/360 ft., one target.
Hit: 11 (1d12 + 4) piercing damage.

Controlled Burst.
Before making one Armalite Rifle attack, the Lieutenant spends 3 ammo.
On a hit, the attack deals 17 (2d12 + 4) piercing damage.
The Lieutenant can use Controlled Burst once per turn.

.45 Pistol.
Ranged Weapon Attack: +7 to hit, range 40/120 ft., one target.
Hit: 10 (1d10 + 4) piercing damage.

Officer Saber.
Melee Weapon Attack: +7 to hit, reach 5 ft., one target.
Hit: 8 (1d8 + 4) slashing damage.
```

##### Bonus Actions

```text
Direct Fire.
Choose one allied Black and Tan within 60 feet who can hear the Lieutenant.
That ally can use its Reaction to make one firearm attack.

Brace.
The Lieutenant gains the Braced condition until the start of its next turn.

Reload.
The Lieutenant reloads one firearm.
```

##### Reactions

```text
Get Down!
When an allied Black and Tan within 30 feet fails a Dexterity saving throw, the Lieutenant can grant that ally a +3 bonus to the save, potentially turning the failure into a success.
```

##### Loot

Recoverable:

* 50% chance: usable Armalite Rifle
* .45 Pistol
* Officer saber
* 1d3 rifle magazines
* 1d2 .45 magazines
* Flak-lined officer coat
* Coded orders
* 100–300 gp equivalent
* 25% chance: command key or safehouse route map

DM note: Lieutenants are the first truly important targets. If players ignore them, the squad gets extra attacks.

---

#### Strong enemy: Black and Tan Captain

**Role:** encounter commander / tactical villain
**CR:** 8, 3,900 XP
**Use count:** 1 per set-piece

```text
Black and Tan Captain
Medium Humanoid, typically Lawful Evil
CR 8, XP 3,900, PB +3

AC 18
HP 145
Speed 30 ft.

STR 15 (+2), DEX 18 (+4), CON 18 (+4), INT 16 (+3), WIS 15 (+2), CHA 18 (+4)

Saving Throws Dex +7, Con +7, Wis +5, Cha +7
Skills Intimidation +10, Insight +5, Perception +5, Persuasion +7
Senses Passive Perception 15
Languages Common plus two Vandergraff regional languages

Gear:
- Armalite Rifle, 4 loaded magazines
- .45 Pistol, 2 loaded magazines
- Officer saber
- Reinforced flak coat
- Command radio
- Sealed arrest warrants
```

##### Traits

```text
Command Net.
While the Captain is conscious and holding or wearing a command radio, Black and Tans within 120 feet ignore the first failed morale check they make.

Hard Target.
If the Captain is behind Half Cover or better, ranged attacks against the Captain do not gain Advantage unless the attacker is within 30 feet.
```

##### Actions

```text
Multiattack.
The Captain makes three attacks, using Armalite Rifle, .45 Pistol, or Officer Saber in any combination.

Armalite Rifle.
Ranged Weapon Attack: +7 to hit, range 120/360 ft., one target.
Hit: 11 (1d12 + 4) piercing damage.

Controlled Burst.
Before making one Armalite Rifle attack, the Captain spends 3 ammo.
On a hit, the attack deals 17 (2d12 + 4) piercing damage.
The Captain can use Controlled Burst once per turn.

.45 Pistol.
Ranged Weapon Attack: +7 to hit, range 40/120 ft., one target.
Hit: 10 (1d10 + 4) piercing damage.

Officer Saber.
Melee Weapon Attack: +7 to hit, reach 5 ft., one target.
Hit: 8 (1d8 + 4) slashing damage.

Condemn the Target.
The Captain chooses one creature it can see within 90 feet.
Until the start of the Captain’s next turn, the first allied Black and Tan to hit that target deals an extra 10 (3d6) damage.
```

##### Bonus Actions

```text
Coordinated Volley.
Choose up to two allied Black and Tans within 60 feet who can hear the Captain.
Each chosen ally can move up to 10 feet or Brace.

Reload.
The Captain reloads one firearm.

Brace.
The Captain gains the Braced condition until the start of its next turn.
```

##### Reactions

```text
Not Yet.
When the Captain fails a saving throw, it can add 1d6 to the roll, potentially turning the failure into a success.
The Captain can use this reaction three times per day.
```

##### Loot

Recoverable:

* 50% chance: usable Armalite Rifle
* .45 Pistol
* Officer saber
* Reinforced flak coat
* Command radio
* 2d4 rifle magazines
* 1d2 .45 magazines
* Sealed arrest warrants
* 300–700 gp equivalent in payroll, bonds, seized valuables, or military scrip
* Intelligence packet pointing to the next Vandergraff operation

##### Reinforced flak coat player-facing loot

```text
Reinforced Flak Coat.
Medium armor, AC 14 + Dex modifier, max Dex +2.
Once per Short Rest, when you take piercing damage from a nonmagical ranged weapon attack, you can reduce the damage by 1d10.
This armor has Disadvantage on Dexterity (Stealth) checks.
```

---

#### Strong enemy: Black and Tan Major

**Role:** session boss / regional commander
**CR:** 9, 5,000 XP
**Use count:** 1, and not in every fight

```text
Black and Tan Major
Medium Humanoid, typically Lawful Evil
CR 9, XP 5,000, PB +4

AC 18
HP 165
Speed 30 ft.

STR 16 (+3), DEX 18 (+4), CON 18 (+4), INT 17 (+3), WIS 16 (+3), CHA 19 (+4)

Saving Throws Str +7, Dex +8, Con +8, Wis +7, Cha +8
Skills Intimidation +12, Insight +7, Perception +7, Persuasion +8
Senses Passive Perception 17
Languages Common plus three Vandergraff regional languages

Gear:
- Armalite Rifle, 4 loaded magazines
- Engraved .45 Pistol, 3 loaded magazines
- Officer saber
- Reinforced flak coat
- Command radio
- Operation ledger
- Signet authority papers
```

##### Traits

```text
Occupation Commander.
Allied Black and Tans within 60 feet who can see or hear the Major gain +2 to morale checks and Wisdom saving throws against being Frightened.

Protected by Rank.
The first time each round that the Major is hit by an attack while within 5 feet of an allied Black and Tan, the ally can choose to take half the damage instead.

No Loose Ends.
When the Major becomes Bloodied, it immediately orders a fallback, execution, fire, alarm, or evidence purge. This is narrative pressure, not free damage.
```

##### Actions

```text
Multiattack.
The Major makes three attacks, using Armalite Rifle, Engraved .45 Pistol, or Officer Saber in any combination.

Armalite Rifle.
Ranged Weapon Attack: +8 to hit, range 120/360 ft., one target.
Hit: 11 (1d12 + 4) piercing damage.

Controlled Burst.
Before making one Armalite Rifle attack, the Major spends 3 ammo.
On a hit, the attack deals 17 (2d12 + 4) piercing damage.
The Major can use Controlled Burst once per turn.

Engraved .45 Pistol.
Ranged Weapon Attack: +8 to hit, range 40/120 ft., one target.
Hit: 10 (1d10 + 4) piercing damage.

Officer Saber.
Melee Weapon Attack: +8 to hit, reach 5 ft., one target.
Hit: 9 (1d10 + 4) slashing damage.

Make an Example.
One creature within 90 feet that can hear the Major must make a DC 16 Wisdom saving throw.
On a failed save, the target is Frightened of the Major until the end of its next turn.
On a successful save, the target is immune to this Major’s Make an Example for 24 hours.
```

##### Bonus Actions

```text
Command Fire.
Choose one allied Black and Tan within 60 feet.
That ally can use its Reaction to make one firearm attack or move up to half its Speed.

Brace.
The Major gains the Braced condition until the start of its next turn.

Reload.
The Major reloads one firearm.
```

##### Reactions

```text
Countermand.
When an allied Black and Tan within 60 feet fails a saving throw, the Major can allow that ally to reroll the save.
The ally must use the new result.

Duck Behind Them.
When the Major is hit by a ranged attack and has an allied Black and Tan within 5 feet, the Major gains +3 AC against that attack, potentially causing it to miss. If the attack misses because of this, the adjacent ally takes 7 piercing damage.
```

##### Loot

Recoverable:

* Armalite Rifle, usable if not destroyed
* Engraved .45 Pistol, valuable and identifiable
* Officer saber
* Reinforced flak coat
* Command radio
* Operation ledger
* Signet authority papers
* 700–1,500 gp equivalent
* One major intelligence asset:

  * safehouse list
  * prison transfer schedule
  * informant ledger
  * armory manifest
  * orders implicating a higher Vandergraff official

DM note: The Major should be hated. Mechanically, he is not impossible; socially, he is a campaign lever.

---

#### Heavy ordnance enemy: Black and Tan SAM-7 Team

**Role:** objective pressure / anti-air / “stop them before they fire” set-piece
**CR:** 8, 3,900 XP
**Use count:** 0–1 per fight

Do **not** use this as an ordinary shooter. The SAM-7 Team should telegraph its intent, take time to lock, and give the party meaningful counterplay.

```text
Black and Tan SAM-7 Team
Medium Humanoid team, typically Lawful Evil
CR 8, XP 3,900, PB +3

AC 15
HP 120
Speed 25 ft.

STR 14 (+2), DEX 16 (+3), CON 16 (+3), INT 15 (+2), WIS 16 (+3), CHA 10 (+0)

Saving Throws Dex +6, Con +6, Int +5, Wis +6
Skills Perception +9, Investigation +5
Senses Passive Perception 19
Languages Common plus one Vandergraff regional language

Gear:
- SAM-7 launcher
- 1 SAM-7 missile
- .45 Pistol, 2 loaded magazines
- Targeting glass
- Field radio
- Heavy ordnance harness
```

##### Traits

```text
Crewed Weapon.
The SAM-7 Team represents two operators. When reduced to half HP or less, it loses one operator and has Disadvantage on Lock-On checks.

Telegraphed Ordnance.
When the team begins Lock-On, visible signs appear: shouted range calls, raised launcher, signal light, magical targeting glint, or radio chatter.
Creatures that can see or hear the team know something dangerous is being prepared.
```

##### Actions

```text
.45 Pistol.
Ranged Weapon Attack: +6 to hit, range 40/120 ft., one target.
Hit: 9 (1d10 + 3) piercing damage.

Lock-On.
The team chooses one visible flying creature, vehicle, siege engine, construct, Huge-or-larger creature, or major object within 600 feet.
The target must not have Total Cover.
The team makes a DC 15 Intelligence check, adding PB.
On a success, the target is Locked until the end of the team’s next turn.

Fire SAM-7.
The team fires at a target currently Locked by this launcher.
The target makes a DC 15 Dexterity saving throw.
On a failed save, the target takes 55 (10d10) fire and force damage.
On a successful save, the target takes half damage.

Creatures within 15 feet of the target must make a DC 15 Dexterity saving throw.
On a failed save, a creature takes 22 (4d10) fire and thunder damage.
On a successful save, it takes half damage.

The missile is consumed.
```

##### Bonus Actions

```text
Reposition Launcher.
The team moves up to 10 feet without provoking Opportunity Attacks, but must end this movement behind cover or adjacent to an allied Black and Tan.

Brace.
The team gains the Braced condition until the start of its next turn.
```

##### Counterplay

The party can stop or spoil the shot by:

| Counterplay                     | Effect                                                                 |
| ------------------------------- | ---------------------------------------------------------------------- |
| Break line of sight             | Lock-On fails or ends                                                  |
| Knock team Prone                | Lock-On check has Disadvantage                                         |
| Destroy/steal targeting glass   | Lock-On check has Disadvantage                                         |
| Drop magical darkness/fog/smoke | Lock-On check fails unless the team has another clear targeting method |
| Deal 40+ damage in one round    | Team must make DC 15 Con save or lose Lock-On                          |
| Kill one operator               | Team has Disadvantage on Lock-On                                       |
| Force movement                  | Lock-On ends                                                           |
| Total Cover                     | Cannot target                                                          |

##### Loot

Recoverable:

* 50% chance: SAM-7 launcher damaged but repairable
* 25% chance: SAM-7 launcher usable but empty
* 10% chance: one intact SAM-7 missile remains, only if the team did not fire
* Targeting glass
* Heavy ordnance harness
* Field radio
* Sealed transport order
* 300–600 gp equivalent

DM note: The SAM-7 is an **encounter object**, not a normal weapon drop. If the party gets one intact missile, that is major campaign treasure.

---

### Recommended encounter packages

#### Package A: Checkpoint Crackdown

**Difficulty:** serious Moderate
**XP:** 29,700
**Enemy count:** 13

| Enemy                            |  Count | XP each |      Total |
| -------------------------------- | -----: | ------: | ---------: |
| Black and Tan Captain            |      1 |   3,900 |      3,900 |
| Black and Tan Lieutenant         |      1 |   2,900 |      2,900 |
| Black and Tan Suppression Gunner |      2 |   2,300 |      4,600 |
| Black and Tan Shield Trooper     |      2 |   1,800 |      3,600 |
| Black and Tan Field Medic        |      1 |   1,800 |      1,800 |
| Black and Tan Rifleman           |      5 |   1,100 |      5,500 |
| Black and Tan Constable          |      5 |     700 |      3,500 |
| **Total**                        | **17** |         | **25,800** |

This is mechanically below the 29,000 Moderate benchmark, but the guns, cover, and suppression make it feel heavier. Use this if the party is entering already wounded or if the battlefield heavily favors the Black and Tans.

##### Better adjusted version for a fresh party

Add:

| Enemy                    | Count | XP each |  Total |
| ------------------------ | ----: | ------: | -----: |
| Black and Tan Lieutenant |    +1 |   2,900 | +2,900 |
| Black and Tan Rifleman   |    +1 |   1,100 | +1,100 |

Adjusted total: **29,800 XP**
Adjusted enemy count: **19**

That is a lot of bodies, so run the constables on one shared initiative.

---

#### Package B: Barracks Yard Set-Piece

**Best default for your party.**
**Difficulty:** Moderate-plus, fair but dangerous
**XP:** 34,400
**Enemy count:** 16

| Enemy                            |  Count | XP each |      Total |
| -------------------------------- | -----: | ------: | ---------: |
| Black and Tan Major              |      1 |   5,000 |      5,000 |
| Black and Tan Captain            |      1 |   3,900 |      3,900 |
| Black and Tan Lieutenant         |      2 |   2,900 |      5,800 |
| Black and Tan Suppression Gunner |      2 |   2,300 |      4,600 |
| Black and Tan Shield Trooper     |      2 |   1,800 |      3,600 |
| Black and Tan Field Medic        |      1 |   1,800 |      1,800 |
| Black and Tan Rifleman           |      4 |   1,100 |      4,400 |
| Black and Tan Constable          |      3 |     700 |      2,100 |
| SAM-7 Team                       |      1 |   3,900 |      3,900 |
| **Total**                        | **17** |         | **35,100** |

This is the one I would use as the primary “Black and Tans are a real threat” battle.

##### Fairness constraints

Use these or it can get mean:

```text
Round 1:
- SAM-7 Team can only Lock-On, not fire.
- Suppression Gunners use Suppressive Fire, not Automatic Sweep.
- Major starts behind cover but not unreachable.
- Captain and Lieutenants must spend bonus actions commanding, not all pure damage.

Round 2:
- SAM-7 Team may fire only if Lock-On survived.
- One Suppression Gunner should reload, reposition, or get disrupted.
- Morale checks begin if either the Major or Captain is Bloodied.

Round 3+:
- If Major and Captain are both down, remaining Black and Tans start withdrawing.
```

---

#### Package C: Convoy Interception

**Difficulty:** mobile tactical fight
**XP:** 31,300 before vehicle/objective adjustments
**Enemy count:** 14

| Enemy                            |  Count | XP each |      Total |
| -------------------------------- | -----: | ------: | ---------: |
| Black and Tan Captain            |      1 |   3,900 |      3,900 |
| Black and Tan Lieutenant         |      2 |   2,900 |      5,800 |
| Black and Tan Suppression Gunner |      1 |   2,300 |      2,300 |
| Black and Tan Shield Trooper     |      2 |   1,800 |      3,600 |
| Black and Tan Field Medic        |      1 |   1,800 |      1,800 |
| Black and Tan Rifleman           |      5 |   1,100 |      5,500 |
| Black and Tan Constable          |      2 |     700 |      1,400 |
| SAM-7 Team                       |      1 |   3,900 |      3,900 |
| **Total**                        | **15** |         | **32,200** |

Use this when there are trucks, prisoners, supply crates, or a bridge objective.

##### Convoy terrain

Use:

* 2–3 wagons/trucks as Half Cover
* 1 armored transport as Three-Quarters Cover
* one ditch, wall, or hedgerow line
* one burning vehicle after round 2
* one escape route the Black and Tans will try to use

##### Objective options

Pick one:

| Objective          | Mechanical effect                                                                      |
| ------------------ | -------------------------------------------------------------------------------------- |
| Rescue prisoners   | 4 noncombatant tokens in transport; Black and Tans lose morale if freed                |
| Capture officer    | Major/Captain tries to flee once Bloodied                                              |
| Stop evidence burn | Field Medic or Constables spend actions destroying documents                           |
| Disable SAM-7      | SAM team tries to target a flying ally, airship, dragon, bridge, or resistance vehicle |
| Steal payroll      | Adds loot but increases reinforcements if fight drags                                  |

---

### Initiative grouping for init-tracker

For a 10-player party, do not roll 17 separate enemy initiatives. Use groups.

```yaml
initiative_groups:
  - group: "Black and Tan Command"
    members:
      - Major
      - Captain
      - Lieutenants

  - group: "Black and Tan Fire Team"
    members:
      - Riflemen
      - Suppression Gunners
      - SAM-7 Team

  - group: "Black and Tan Line"
    members:
      - Constables
      - Shield Troopers
      - Field Medic
```

If the table is moving slowly, merge further:

```yaml
initiative_groups_fast:
  - group: "Officers"
  - group: "Troopers"
```

---

### Tactical behavior scripts

#### Constables

```text
Default:
- Stay in pairs.
- Fire pistols from cover.
- Grapple only isolated or Prone PCs.
- Retreat if both officers are down.

Do not:
- Chase the strongest melee PC alone.
- Waste turns firing at high-AC targets behind cover.
```

#### Riflemen

```text
Default:
- Start behind Half Cover.
- Use Single Shot unless Braced.
- Controlled Burst against exposed targets or wounded casters.
- Reload before empty if safe.

Do not:
- All burst-fire the same PC in round 1.
```

#### Shield Troopers

```text
Default:
- Protect Major, Captain, Medic, or SAM-7 Team.
- Use Shield Bash to create space.
- Form doorway blocks.
- Use Interpose Shield every round if possible.

Do not:
- Become static walls forever. They should move under pressure.
```

#### Suppression Gunners

```text
Default:
- Round 1: Suppressive Fire to shape movement.
- Round 2: Single shots or reload.
- Round 3: Suppressive Fire again if still Braced.
- Automatic Sweep only when 3+ PCs are exposed.

Do not:
- Chain Suppressive Fire every round from multiple gunners onto the same area.
```

#### Field Medic

```text
Default:
- Preserve officer.
- Smoke exposed command positions.
- Use Stimulant Ampoule on Shield Trooper or Captain.
- Flee with documents when Bloodied.

Do not:
- Stand in the open healing mooks.
```

#### Lieutenants

```text
Default:
- Use Direct Fire once per round.
- Keep Riflemen coordinated.
- Fight aggressively if Captain is alive.
- Retreat if Captain and Major are down.

Do not:
- Spend every turn doing only personal attacks.
```

#### Captain

```text
Default:
- Uses Condemn the Target on the most disruptive PC.
- Uses Coordinated Volley to reposition troops.
- Falls back if Bloodied and Major is down.
- Tries to preserve command radio.

Do not:
- Stand still trading shots until dead.
```

#### Major

```text
Default:
- Opens with Make an Example.
- Uses Command Fire on Suppression Gunner or Lieutenant.
- Uses subordinates as protection.
- Orders retreat/evidence purge when Bloodied.

Do not:
- Fight honorably.
```

#### SAM-7 Team

```text
Default:
- Round 1: Lock-On.
- Round 2: Fire only if Lock-On survives and target is valid.
- If disrupted, reposition and try again.
- If missile is fired or lost, switch to pistol and retreat.

Do not:
- Fire untelegraphed at clustered PCs.
- Use as normal anti-personnel spam.
```

---

### Battlefield layout guidance

For a fair large-party fight, use at least:

| Terrain feature                | Count |
| ------------------------------ | ----: |
| Half Cover positions           |  8–12 |
| Three-Quarters Cover positions |   2–4 |
| Elevated firing points         |   1–2 |
| Flanking routes                |     2 |
| Heavy doors / gates            |   1–3 |
| Objective zones                |   2–3 |
| Smoke or obscuring option      |   1–2 |
| Ammunition or evidence cache   |     1 |

Avoid a giant empty field. A giant empty field makes guns unfair.

#### Good locations

* police barracks yard
* checkpoint at a bridge
* occupied manor converted into command post
* rail depot
* warehouse arms cache
* courthouse square
* prison transfer convoy
* burned-out village street
* dockyard checkpoint
* manor gatehouse

---

### Loot package tables

#### Standard loot by enemy type

| Enemy              | Normal drops                                                        |
| ------------------ | ------------------------------------------------------------------- |
| Constable          | .45 pistol chance, baton, manacles, 1d2 mags                        |
| Rifleman           | Armalite chance, 1d3 mags, knife, field radio scrap                 |
| Shield Trooper     | ballistic shield, .45 pistol, breaching tools                       |
| Suppression Gunner | damaged heavy Armalite parts, box magazine, ammo satchel            |
| Field Medic        | medical kit, smoke canisters, field treatment charges               |
| Lieutenant         | Armalite, .45 pistol, officer saber, coded orders                   |
| Captain            | Armalite, .45 pistol, command radio, warrants, reinforced flak coat |
| Major              | engraved .45, Armalite, ledger, signet papers, major intelligence   |
| SAM-7 Team         | launcher chance, targeting glass, harness, maybe missile            |

---

#### Usable weapons recovered per encounter

To keep the party from instantly becoming a full modern platoon, use this cap:

```text
After a major Black and Tan fight, no more than:
- 2 usable Armalite Rifles
- 3 usable .45 Pistols
- 1 usable specialty weapon
- 0–1 SAM-7 missile-related item

All other firearms are:
- damaged
- jammed
- missing parts
- keyed to Vandergraff ammunition
- magically tracked
- politically dangerous to carry
```

This keeps loot exciting without flooding the campaign.

---

#### Damaged firearm repair rule

```text
Damaged Firearm.
A damaged firearm cannot be used until repaired.

Repair requires:
- appropriate tools
- 4 hours of work
- parts worth 20% of the item’s value
- DC 15 Intelligence check using Tinker’s Tools, Smith’s Tools, or relevant firearm proficiency

Failure by 5 or more consumes half the parts.
```

For init-tracker, damaged gear should be loot metadata, not a combat object.

---

### Special loot items

#### Vandergraff Command Radio

```text
Vandergraff Command Radio
Wondrous item / technological item, uncommon or rare

This device allows short-range coded communication with other Vandergraff radios in the area.
It does not automatically reveal enemy channels unless the user has a code sheet or succeeds on an Intelligence check.

Suggested checks:
- DC 13 to listen to open chatter
- DC 16 to impersonate a routine signal
- DC 18 to issue a false order during combat
- DC 20 to decode encrypted command traffic
```

Failure can alert nearby Black and Tans.

#### Coded Orders

```text
Coded Orders
Valuable intelligence

Can be used to:
- reveal the next checkpoint
- identify a collaborator
- locate a prisoner convoy
- give Advantage on one infiltration check
- reduce DCs when using a Vandergraff radio
```

#### Officer Warrants

```text
Sealed Arrest Warrants
Campaign evidence

These prove Vandergraff intends to arrest, relocate, execute, or interrogate named NPCs.
They are more valuable as leverage than as money.
```

#### Operation Ledger

```text
Operation Ledger
Major campaign loot

Contains:
- payroll records
- bribes
- informant aliases
- raid schedules
- ammunition transfers
- prisoner movements
- commander signatures
```

This should point to the next adventure.

#### Black and Tan Flak Coat

```text
Black and Tan Flak Coat
Medium armor

AC 13 + Dex modifier, max Dex +2.
No Strength requirement.
Disadvantage on Dexterity (Stealth) checks only if worn with helmet and full kit.

Once per Long Rest, when you take piercing damage from a nonmagical ranged weapon, reduce the damage by 1d6.
After reducing damage this way, the coat becomes Damaged until repaired.
```

#### Reinforced Flak Coat

```text
Reinforced Flak Coat
Medium armor, rare

AC 14 + Dex modifier, max Dex +2.
Disadvantage on Dexterity (Stealth) checks.

Once per Short Rest, when you take piercing damage from a nonmagical ranged weapon, reduce the damage by 1d10.
```

#### Ballistic Shield

```text
Ballistic Shield
Shield, uncommon

Requires Strength 13.
You gain the normal +2 AC bonus from a shield.

As a Bonus Action, choose one direction.
Until the start of your next turn, ranged attacks from that direction treat you as having Half Cover.

You have Disadvantage on Dexterity (Stealth) checks while wielding this shield.
```

#### Smoke Canister

```text
Smoke Canister
Adventuring gear, consumable

As an Action, throw this canister to a point within 30 feet.
A 10-foot-radius sphere centered on that point becomes Heavily Obscured until the end of your next turn.
A strong wind, magical gust, or similar effect disperses it early.
```

Keep smoke short-duration. Long smoke clouds can bog down a huge fight.

---

### Encounter balance tuning knobs

#### To make the fight easier

Use any two:

```text
- Remove one Suppression Gunner.
- Remove one Lieutenant.
- Make the SAM-7 Team start without Lock-On equipment.
- Reduce all enemy magazines by half.
- Make the Field Medic flee once Bloodied.
- Have morale checks trigger when Captain is Bloodied instead of dropped.
- Start 30–40% of enemies out of position.
```

#### To make the fight harder

Use only one at a time:

```text
- Add one Lieutenant.
- Add two Riflemen.
- Add one Suppression Gunner.
- Give the Captain one prepared overwatch lane.
- Add a second Field Medic.
- Let the SAM-7 Team start with a partial Lock-On, needing only one successful action.
```

Do **not** add more than one hardening knob unless you want this to be a potential TPK.

---

### Strong recommendation for your first Black and Tan fight

Use **Package B: Barracks Yard Set-Piece**, but soften the opening:

```text
Round 1:
- Major uses Make an Example.
- Captain uses Coordinated Volley.
- Lieutenants use Direct Fire.
- Suppression Gunners use Suppressive Fire.
- Riflemen use mostly Single Shot.
- SAM-7 Team starts Lock-On against a flying ally, vehicle, huge summon, tower, or escape route — not a random PC.

Round 2:
- Players should have clear options:
  - kill/disrupt SAM-7 Team
  - rush Suppression Gunners
  - break command radio
  - isolate Major
  - rescue prisoners
  - seize evidence
  - use smoke or magic to break line of sight

Round 3:
- Morale starts cracking if officers are Bloodied.
- Enemies begin falling back by role, not fighting to the last man.
```

That gives the Black and Tans teeth without making the party feel ambushed by unavoidable modern damage.

---

### init-tracker tags and fields

Suggested tags:

```yaml
tags:
  faction: vandergraff_black_and_tans
  creature_type: humanoid
  era_style: modernish_1970s
  combat_style:
    - firearms
    - cover
    - suppression
    - command_structure
    - morale
```

Suggested enemy fields:

```yaml
firearm_user: true
uses_magazines: true
tracks_ammo: true
can_reload_bonus_action: true
can_brace: true
can_jam: true
loud_weapon: true
morale_group: black_and_tans
commander_dependent: true
```

Suggested action IDs:

```yaml
actions:
  - firearm_single_shot
  - firearm_controlled_burst
  - firearm_suppressive_fire
  - firearm_automatic_sweep
  - firearm_reload
  - firearm_brace
  - officer_direct_fire
  - officer_coordinated_volley
  - medic_field_treatment
  - shield_interpose
  - sam7_lock_on
  - sam7_fire
```

Suggested conditions:

```yaml
conditions:
  - braced
  - suppressed
  - jammed
  - locked_on
  - morale_shaken
  - bloodied
```

Suggested loot metadata:

```yaml
loot_state:
  - usable
  - damaged
  - repairable
  - empty
  - serialized
  - politically_dangerous
  - plot_item
```

---

### Final DM note

The best version of this enemy faction is not “modern guns beat fantasy.” It is:

```text
The Black and Tans are terrifying when organized.
They become beatable when the party breaks command, cover, ammo, morale, and line of sight.
```

That gives your level-11 party a real tactical challenge while still letting them feel like powerful D&D heroes.

[1]: https://roll20.net/compendium/dnd5e/Rules%3ACombat%20Encounters "Combat Encounters | D&D 2024 | Roll20 Compendium"
[2]: https://www.dndbeyond.com/sources/dnd/free-rules/equipment "Equipment - D&D Beyond Basic Rules - Dungeons & Dragons - Sources - D&D Beyond "
[3]: https://roll20.net/compendium/dnd5e/Rules%3AParts%20of%20a%20Stat%20Block "Parts of a Stat Block | D&D 2024 | Roll20 Compendium"
[4]: https://www.dndbeyond.com/sources/dnd/br-2024/how-to-use-a-monster?srsltid=AfmBOopcaihZkv5c29IN2vhoEoyMztfUVG9KYV19nWC0USScGNJqWTn9&utm_source=chatgpt.com "How to Use a Monster"

---

## 39. Maintenance notes
This document should be updated after each implementation pass.

After each pass, append a short note under this section:

```text
Date:
Pass:
Files changed:
Behavior added:
Tests run:
Known limitations:
Next recommended pass:
```

### Change log

#### 2026-05-05 — Added Vandergraff Black and Tans enemy package

Merged the Vandergraff “Black and Tans” enemy package into the living firearm plan, including encounter philosophy, enemy stat blocks, loot packages, tactical behavior scripts, and init-tracker tags/fields for future implementation passes.

#### 2026-05-01 — Initial living plan

Created initial firearm subsystem plan for init-tracker using the user’s weapon names:

- Armalite Rifles
- .45 Pistols
- SAM-7 Missiles

Initial plan includes rules, implementation phases, data shapes, UI requirements, event logs, testing strategy, tuning knobs, and agent-ready pass breakdown.

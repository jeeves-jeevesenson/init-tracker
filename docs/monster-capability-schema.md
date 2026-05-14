# Monster Capability Schema

## 1. Purpose
The purpose of this schema is to provide a normalized, executable representation of monster capabilities (actions, traits, reactions, etc.) that can be consumed by the future DM monster-control UI and backend actor-command engine.

## 2. Relationship to Legacy Monsters/*.yaml
- Legacy YAMLs (`Monsters/*.yaml`) are treated as display-only source data.
- Normalized capabilities (stored in `monster_capabilities/`) act as an overlay or enhancement.
- The backend will prefer normalized executable data when available, falling back to legacy display text.

## 3. Source/Import Strategy
- **Primary Source:** Open5e (V2) for comprehensive structured data.
- **Secondary Source:** dnd5eapi.co for SRD baseline validation.
- **Legacy Source:** Existing `Monsters/*.yaml` for custom/AideDD-specific data.
- **Normalization:** A Python-based importer (`scripts/importers/monster_capability_import.py`) maps source fields to this schema.

## 4. Licensing & Provenance
- All generated capability files must include `source` and `license` fields.
- Content must adhere to CC-BY-4.0 (SRD 5.1 / 5.2.1) or other open licenses.
- No proprietary/Product Identity content (e.g., Beholders, Mind Flayers) should be imported from non-open sources without a specific license.

## 5. Normalized Top-Level Fields
- `name`: Display name (e.g., "Aboleth").
- `slug`: Unique identifier (e.g., "aboleth").
- `source`: Provenance info (e.g., "Open5e", "SRD 5.2.1").
- `license`: License type (e.g., "CC-BY-4.0").
- `capabilities`: A list of executable capability objects.

## 6. Capability Object Shape
Each capability object includes:
- `id`: Unique ID within the monster (e.g., "tentacle-attack").
- `name`: Display name (e.g., "Tentacle").
- `type`: Category (`action`, `bonus_action`, `reaction`, `legendary_action`, `trait`, `lair_action`, `special`).
- `executable`: Boolean (true if the backend can automate this).
- `desc`: Display description (preserving markup).
- `action_type`: `melee_attack`, `ranged_attack`, `save_ability`, `utility`, `composite` (multiattack).
- `recharge`: Optional (e.g., `5` for 5-6, `short_rest`, `long_rest`).
- `cost`: Action cost (default 1).
- `mechanics`: Structured data for the backend (see below).
- `warnings`: Optional list of importer quality warnings for useful manual review notes.

### 6.1 Mechanics Shape (Examples)

#### Simple Attack
```yaml
mechanics:
  attack_bonus: 9
  damage:
    - formula: "2d6 + 5"
      type: "bludgeoning"
```

#### Save-based AoE
```yaml
mechanics:
  save_dc: 14
  save_ability: "dex"
  shape: "cone"
  size: 30
  damage:
    - formula: "8d6"
      type: "fire"
      on_save: "half"
```

#### Multiattack (Composite)
Multiattack is a parent action that guides a sequence of child actions.

```yaml
mechanics:
  composite:
    - action_id: "tentacle-attack"
      count: 3
    # sequence_kind defaults to "fixed_children" when composite is a list
```

**Choose-N sequence:**
```yaml
mechanics:
  composite:
    sequence_kind: "choose_n"
    choose_n: 2 # Total budget of selections from the list
    children:
      - action_id: "pistol"
        count: 2 # Max allowed of this type
      - action_id: "baton"
        count: 2
```

**Object-based fixed sequence (alternative):**
```yaml
mechanics:
  composite:
    sequence_kind: "fixed_children"
    children:
      - action_id: "bite"
        count: 1
      - action_id: "claw"
        count: 2
```

#### Modifier Actions
Modifier actions do not resolve an attack themselves but apply a state or bonus to the next relevant action.

```yaml
id: "controlled-burst"
name: "Controlled Burst"
type: "action"
action_type: "modifier"
mechanics:
  modifier:
    kind: "next_attack"
    ammo_cost: 3
    damage_bonus:
      extra_weapon_dice: 1 # adds one base weapon die
    limit: "once_per_turn"
    jam_risk: true # natural 1 on the modified attack jams the weapon
```

#### Effects / Riders
```yaml
mechanics:
  effects:
    - kind: "condition"
      condition: "prone"
      trigger: "on_failed_save"
      save_ability: "str"
      save_dc: 11
      text: "The target is knocked prone."
```

#### Spellcasting
```yaml
type: "trait" # or action
action_type: "spellcasting"
executable: false
name: "Spellcasting"
mechanics:
  spellcasting:
    ability: "int"
    save_dc: 17
    attack_bonus: 9
    lists:
      - frequency: "at_will"
        spells: ["detect-magic", "mage-hand"]
      - frequency: "daily"
        uses: 1
        spells: ["time-stop"]
      - frequency: "slot"
        level: 1
        slots: 4
        spells: ["magic-missile", "shield"]
```

#### Limited Uses (Generic)
```yaml
mechanics:
  uses:
    max: 3
    per: "day" # or "long_rest", "short_rest"
```

#### Import Quality Warnings
```yaml
warnings:
  - code: "manual_resolution_required"
    detail: "Conditional trait/action remains display-only."
```

Warnings are intentionally sparse. They identify places where the source text was preserved but the importer could not safely produce executable mechanics, such as unmatched multiattack children, uncertain damage typing, ambiguous condition text, or manual conditional traits.

## 7. Resource Tracking (In-Memory)
The backend tracks the current state of limited-use resources in-memory during the session.
- **Recharge**: Tracks `ready` or `used`.
- **Uses**: Tracks `remaining` vs `max`.
- **Spell Slots**: Tracks `remaining` slots per level.
- **Daily Spells**: Tracks `remaining` uses per spell list group.
- **Multiattack Sequences**: Tracks `total_completed`, `choose_n` budget, and per-child `completed` vs `max` counts. Enforcement occurs during `/resolve-targets` (Apply Results).

DM UI provides buttons to spend, roll, or restore these resources. State is reset on server restart. Sequence state is cleared on turn advance or actor change.

## 8. Effect Trigger Types
- `on_hit`: Applied when an attack hits.
- `on_failed_save`: Applied when a target fails a saving throw.
- `on_failed_escape`: Applied when a target fails to escape a grapple.
- `on_start_turn`: Applied at the start of a target's turn.
- `on_end_turn`: Applied at the end of a target's turn.
- `manual`: Applied explicitly by the DM.

## 8. Target Model
- `self`: The actor itself.
- `single`: One target combatant.
- `multiple`: Specific number of targets.
- `area_manual`: Area of effect (cone, line, sphere, radius, etc.) resolved by DM-selected target rows.

The current assisted multi-target workflow is manual-selection only. The backend may expose area metadata such as `shape`, `size`, and `range`, but it does not derive targets from map geometry.

## 8.1 Assisted Multi-Target Resolution
Save/area capabilities can return a reusable resolution packet containing save DC, save ability, area metadata, rolled full damage, computed successful-save damage, and supported condition riders.

DM target rows use explicit outcomes:
- `fail`: failed save / full failed-save outcome.
- `success`: successful save / successful-save outcome.
- `no_effect`: no damage or effects.
- `manual`: DM notes or externally resolved outcome.

Damage and effects are only applied when the DM explicitly requests `apply_damage` and/or `apply_effects` through the assisted endpoint. The workflow does not roll individual saves, auto-select targets, or consume resources outside the existing execute/resource flow.

## 9. Condition/Effect Model
- `conditions`: List of conditions to apply (e.g., `prone`, `poisoned`).
- `duration`: Duration in rounds or until a specific event (e.g., `end_of_next_turn`).
- `escape_dc`: DC for escaping a grapple/restraint.

## 10. Compatibility & Overlay
- If a monster in the tracker matches a `slug` in the capability store, the capabilities are loaded.
- The UI renders these as actionable buttons/cards.

## 11. Non-Goals for this Pass
- Full implementation of the DM UI.
- Automation of complex "If X then Y" logic in descriptions.
- Modification of player characters.
- Full spellcasting automation.

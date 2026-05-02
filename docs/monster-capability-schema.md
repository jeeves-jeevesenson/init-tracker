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
- **Normalization:** A Python-based importer (`scripts/import/monster_capability_import.py`) maps source fields to this schema.

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
```yaml
mechanics:
  composite:
    - action_id: "tentacle-attack"
      count: 3
```

## 7. Target Model
- `self`: The actor itself.
- `single`: One target combatant.
- `multiple`: Specific number of targets.
- `aoe`: Area of effect (cone, line, sphere, etc.).

## 8. Condition/Effect Model
- `conditions`: List of conditions to apply (e.g., `prone`, `poisoned`).
- `duration`: Duration in rounds or until a specific event (e.g., `end_of_next_turn`).

## 9. Compatibility & Overlay
- If a monster in the tracker matches a `slug` in the capability store, the capabilities are loaded.
- The UI renders these as actionable buttons/cards.

## 10. Non-Goals for this Pass
- Full implementation of the DM UI.
- Automation of complex "If X then Y" logic in descriptions.
- Modification of player characters.

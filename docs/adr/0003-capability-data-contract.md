# ADR 0003: Capability Data Contract

Status: Proposed
Date: 2026-05-22

## Context

The application frequently distinguishes between "static" data (such as the global lists of spell presets) and "dynamic" data (such as current HP or slot values).

However, there is a third, high-value category: **Capability Data**. Capability data defines what a specific player *can* see, use, or do. It is not purely static (as players can change their prepared spells, equip weapons, or unlock resources) and not purely dynamic (it does not change frame-by-frame during combat).

Examples of Capability Data:
- The player's current spellbook / spell selections.
- The available spell catalog for their class/character in the "Manage Spells" overlay.
- Active resource pool definitions (e.g., Focus Points, Ki, Action Surge).
- Inventory, equipment, and active weapon slots.
- Tactical attack options and action features/buttons.

In previous passes, capability data was repeatedly lost because the system treated it either as purely dynamic (allowing delta states to overwrite it) or as purely static (failing to load it dynamically on player connection/reconnection).

Furthermore, restrictive filtering of spell lists based on class/subclass caused major usability blockers at the table (e.g., players being unable to add destructive spells that they legally possessed through homebrew or special subclass grants, such as Stihiya and Destructive Wave).

## Decision

We establish a formal **Capability Data Contract** to govern player capabilities:

1. **Definition of Capability Data:**
   Capability data is explicitly defined as:
   - Spell catalog access and the Manage Spells selector.
   - Player-specific spell selections (known, prepared, and manual).
   - Resource pool definitions (type, display name, reset cadence).
   - Inventory lists, equipped weapons, and wearable slot profiles.
   - Character features, action buttons, and monk-style martial techniques.

2. **Durable Survival Rule:**
   Capability data must survive dynamic state updates. High-frequency combat changes (e.g., HP damage, movement, turn progression) must never strip or omit capability schemas.

3. **Seeded Player First-Load Obligation:**
   First-load payloads (both `static_data` and full `state` payloads) served to clients must include complete capability profiles for all seeded players immediately. No player panel may show empty spellbooks or missing weapon slots on cold startup.

4. **Open Manage Spells Catalog Policy:**
   - The "Manage Spells" tab must expose the entire spell catalog.
   - Players are trusted. Players may add *any* spell from the catalog.
   - Class, subclass, and homebrew filters are tags and suggestions only; they must never act as hard blockers restricting additions.

## Consequences

### Positive
- **No More Empty UIs:** Caster tabs and weapon panels will load instantly and remain populated across combat events and page reloads.
- **Unblocked Gameplay:** Subclass and homebrew spells (like Destructive Wave for Stihiya) can be added seamlessly by players without manual database hacking or complex subclass gating.
- **Clear Developer Invariants:** Clearly maps out which data must be provided by the server during connection handshake.

### Negative
- **Larger Handshake Payloads:** The initial static payload size increases slightly by carrying seeded inventory and spells, which is highly acceptable given the reliability payoff.

### Operational
- Remove restrictive spell filtering in `assets/web/lan/index.html` or `player_command_service.py` spell management paths.
- Ensure `LanController._static_data_payload` backfills spell selections, resource pools, and equipped weapons directly from the player profiles on initial connection.

## Contract / Tests Required

- `test_lan_first_load_spell_catalog_non_empty`: Ensures the global spell presets list is loaded.
- `test_manage_spells_full_catalog_available`: Asserts that any spell from the catalog can be queried in the Manage Spells interface.
- `test_subclass_grants_are_tags_not_hard_filters`: Asserts that subclass spell grants do not block arbitrary additions.
- `test_inventory_payload_non_empty_for_seeded_equipment_user`: Asserts that inventory is populated on cold load.
- `test_equipped_weapon_selected_for_attack`: Asserts that configured weapon data overrides unarmed fallback.

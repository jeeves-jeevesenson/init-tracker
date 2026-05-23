# Contract Test Plan

This document establishes the test plan to ensure stable, regression-proof contract enforcement between backend state/payloads and frontend rendering. It covers schema alignment, initial data load guarantees, partial-update non-clobbering, class features, resource restoration, and player commands.

---

## Contract Groups

### 1. LAN First-Load Capability Contract
- **Purpose:** Ensure that when a player connects or reconnects, the initial static handshake payload carries all required player capability definitions (spell lists, resource structures, inventories) for seeded characters.
- **Current Related Tests:** `tests/test_lan_snapshot_static.py`, `tests/test_lan_spellbook_contract_ui.py`
- **Missing Tests:** Verification that the spell presets and player-specific lists backfill automatically on empty cache hits.
- **Proposed Exact Test Names:**
  - `test_lan_first_load_spell_catalog_non_empty`
  - `test_lan_first_load_player_spells_for_seeded_caster`
  - `test_lan_first_load_resource_pools_for_seeded_resource_user`
- **Fixtures/Data Needed:** Initiative tracker instance with seeded warlock (Vicnor) and seeded caster (Alice) with standard spells and resource definitions loaded in memory.
- **Production Bug It Prevents:** P0-001 (Empty spells list for casters on connection) and P0-002 (Intermittent missing resource dropdowns).
- **Gate/Workstream:** Gate 2 / Workstream B.

---

### 2. LAN Partial-Update Non-Clobber Contract
- **Purpose:** Ensure that dynamic delta packets sent during combat ticks do not overwrite existing, rich client capability structures with empty objects (`{}`) or empty arrays (`[]`).
- **Current Related Tests:** `tests/test_lan_snapshot_cache.py` (has partial tests)
- **Missing Tests:** Hardened frontend merge asserts and backend delta snapshots carryover assertions.
- **Proposed Exact Test Names:**
  - `test_lan_state_delta_does_not_clear_spell_capabilities`
  - `test_resource_pools_survive_state_delta`
  - `test_reconnect_resource_pools_present_without_multiple_refreshes`
- **Fixtures/Data Needed:** Client state mock loaded with active spell catalog and player spells, receiving stripped `lan_state_delta` packages.
- **Production Bug It Prevents:** Spells and resources disappearing mid-combat after movement, turn advancement, or reconnection.
- **Gate/Workstream:** Gate 3 / Workstream B.

---

### 3. DM State Serialization Contract
- **Purpose:** Guarantee that nested Python models (such as combatants, active conditions, rolls) are serialized as clean, JSON-safe structures without throwing type errors or dropping data.
- **Current Related Tests:** `tests/test_dm_combat_service.py`
- **Missing Tests:** Explicit checks for nested dictionary structures and sibling field survival.
- **Proposed Exact Test Names:**
  - `test_dm_state_serialization_nested_safety`
  - `test_dm_state_serialization_retains_sibling_fields`
- **Fixtures/Data Needed:** A fully populated combat instance containing custom NPCs, condition overlays, and complex action history.
- **Production Bug It Prevents:** Sudden backend crash or traceback when broadcasting grid or combatant states.
- **Gate/Workstream:** Gate 2 / Workstream B.

---

### 4. /dm/map Startup Contract
- **Purpose:** Ensure that the tactical map initialization endpoint correctly serves player profile catalogs and map settings, even when the active combat roster is blank.
- **Current Related Tests:** `tests/test_dm_map_startup_contract.py`
- **Missing Tests:** Verification that adding player profiles hydrates the combatant list.
- **Proposed Exact Test Names:**
  - `test_dm_map_startup_catalog_populated_when_roster_blank`
  - `test_dm_map_startup_hydrate_roster_on_profile_addition`
- **Fixtures/Data Needed:** Empty session startup state, loaded presets library.
- **Production Bug It Prevents:** Empty roster blocking tactical setup or console rendering.
- **Gate/Workstream:** Gate 2 / Workstream B.

---

### 5. Resource/Rest Contract
- **Purpose:** Verify that a Long Rest command restores eligible resources (Focus Points, spell slots, pact slots, hit points) to maximum values while preserving manual rest-independent resources.
- **Current Related Tests:** `tests/test_combat_service_long_rest.py`, `tests/test_resource_pool_accounting.py`
- **Missing Tests:** Reset-cadence rest verification and broadcast checks.
- **Proposed Exact Test Names:**
  - `test_long_rest_resource_values_reflect_backend_after_payload`
  - `test_long_rest_restores_long_rest_pool`
  - `test_long_rest_does_not_restore_manual_pool`
- **Fixtures/Data Needed:** Seeds for a Level 10 Monk (Old Man) and a Caster (Alice) with depleted resources and Focus Points.
- **Production Bug It Prevents:** P0-003 and P0-004 (Long rest hangs app, takes too long, or fails to restore pools).
- **Gate/Workstream:** Gate 5 / Workstream D.

---

### 6. Inventory/Equipment Contract
- **Purpose:** Ensure that seeded inventory weapons are successfully parsed, equipped weapons are mapped to active attacks, and the resolver uses the equipped weapon instead of defaulting to Unarmed Strike.
- **Current Related Tests:** `tests/test_items_weapon_resolution.py`, `tests/test_inventory_weapon_assignment_api.py`
- **Missing Tests:** Fallback-reason logging, weapon presence in initial payloads, and automatic attack select checks.
- **Proposed Exact Test Names:**
  - `test_inventory_payload_non_empty_for_seeded_equipment_user`
  - `test_equipped_weapon_selected_for_attack`
  - `test_configured_weapon_prevents_unarmed_fallback`
  - `test_unarmed_fallback_requires_fallback_reason`
- **Fixtures/Data Needed:** Caster profile for John Twilight containing custom equipped Longsword, starting combat with active attacks.
- **Production Bug It Prevents:** P0-005 (John Twilight falling back to Unarmed Strike with empty inventory).
- **Gate/Workstream:** Gate 6 / Workstream E.

---

### 7. Pact Slot Current/Max Contract
- **Purpose:** Ensure that Pact Magic slots are modeled correctly where current cast counts decrement the current slots value while leaving max slots unaltered. Manual current overrides must not corrupt max.
- **Current Related Tests:** `tests/test_pact_magic_spell_slots.py`
- **Missing Tests:** Explicit manual override tests for pact slots.
- **Proposed Exact Test Names:**
  - `test_pact_cast_decrements_current_not_max`
  - `test_pact_manual_current_override_preserves_max`
  - `test_pact_current_override_cannot_delete_max`
  - `test_pact_long_rest_restores_current_to_max`
- **Fixtures/Data Needed:** Seeded warlock profile for Vicnor with Pact slots configured (e.g. 2 slots of 3rd level).
- **Production Bug It Prevents:** P0-007 (Vicnor's manual override or cast corrupting pact slot max value).
- **Gate/Workstream:** Gate 5 / Workstream D.

---

### 8. DM/LAN Sync Contract
- **Purpose:** Guarantee that mutations initiated on either the DM surface (e.g. NPC movement) or the player page (e.g. ending turn) trigger prompt state synchronizations.
- **Current Related Tests:** `tests/test_lan_reconnect_recovery.py`
- **Missing Tests:** Explicit DM-to-LAN movement propagation checks and player-to-DM turn end propagation checks.
- **Proposed Exact Test Names:**
  - `test_dm_movement_propagates_to_lan_instantly`
  - `test_player_end_turn_advances_dm_initiative`
- **Fixtures/Data Needed:** Multi-client websocket test harness connecting both a DM and player client.
- **Production Bug It Prevents:** Latency or synchronization dropouts mid-combat.
- **Gate/Workstream:** Gate 2 / Workstream B.

---

### 9. Player-Facing Log vs Debug Trace Contract
- **Purpose:** Ensure that combat event log records are cleanly formatted for player consumption while dense, complex action payloads (like rollback logs or performance spans) are isolated to system debug files.
- **Current Related Tests:** `tests/test_debug_trace_instrumentation.py`
- **Missing Tests:** Separation assertion between logs.
- **Proposed Exact Test Names:**
  - `test_combat_log_excludes_system_debug_traces`
  - `test_system_debug_traces_contain_performance_metrics`
- **Fixtures/Data Needed:** Active combat encounter generating spellcasts and rolls.
- **Production Bug It Prevents:** P2-001 (Player-facing overflow debug text rendering in user panel).
- **Gate/Workstream:** Gate 4 / Workstream C.

---

### 10. Open Manage Spells Catalog & Subclass Contract
- **Purpose:** Ensure that the Manage Spells catalog is open and allows the addition of arbitrary spells from the presets database, treating class and subclass suggestions as suggestions rather than hard blocks.
- **Current Related Tests:** `tests/test_lan_spellbook_contract_ui.py`
- **Missing Tests:** Manual spell addition unblocking tests.
- **Proposed Exact Test Names:**
  - `test_manage_spells_allows_arbitrary_spell_add`
  - `test_manage_spells_empty_catalog_is_error_not_silent_empty`
  - `test_stihiya_can_add_destructive_wave_from_catalog`
  - `test_subclass_grants_are_tags_not_hard_filters`
- **Fixtures/Data Needed:** Seeded spell catalog including "Destructive Wave" and character profile for Stihiya.
- **Production Bug It Prevents:** P1-001 (Stihiya unable to select/cast Destructive Wave due to subclass gating).
- **Gate/Workstream:** Gate 8 / Workstream G.

---

### 11. Monk Fury of Blows & Action Pipeline Contract
- **Purpose:** Verify that monk combat features (Attack + Flurry/Fury of Blows) resolve the correct number of attacks (5 attacks at level 10+), spend focus points correctly, generate clear logs, and are duplicate-safe.
- **Current Related Tests:** `tests/test_player_feature_execution.py`
- **Missing Tests:** Multi-attack monk assertions and double-click protection checks.
- **Proposed Exact Test Names:**
  - `test_level10_monk_attack_plus_flurry_resolves_five_attacks`
  - `test_flurry_spends_one_focus_point`
  - `test_flurry_log_names_feature`
  - `test_fury_trace_records_expected_and_actual_attack_count`
  - `test_duplicate_flurry_click_does_not_double_process`
- **Fixtures/Data Needed:** Seeded Level 10 Monk (Old Man) profile with active combat targets.
- **Production Bug It Prevents:** P0-006 (Old Man Fury of Blows slow, missing attacks, vague logging).
- **Gate/Workstream:** Gate 7 / Workstream F.

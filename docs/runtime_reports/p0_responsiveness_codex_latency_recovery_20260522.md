# P0-RESPONSIVENESS Codex Latency Recovery

Date: 2026-05-22

## Dirty Tree / WIP Preservation

- Preserved the existing dirty tree. No `git reset`, checkout, clean, commit, or push was run.
- Saved the pre-Codex WIP diff at `docs/runtime_reports/wip_diffs/pre_codex_latency_wip_20260522_210426.diff`.
- Existing user/prior-agent WIP was kept, including LAN action acknowledgements/idempotency, partial snapshot non-clobbering, broadcast invalidation tests, and inventory weapon-resolution tests.

## Lost-Session Findings Validated Or Corrected

- Validated from `logs/debug-trace-20260522-202252.jsonl` that `_store_character_yaml` was a major equip/unequip cost: observed spans include 1944.507ms and 3146.411ms.
- Validated that equip/unequip HTTP requests were mostly route-level only before this pass: Fred bandolier equip/unequip routes recorded ~2028ms+ HTTP spans with no detailed inventory mutation span.
- Validated that static rebuilds were still possible from `player_yaml_write:profile_structure,static_capabilities,dynamic_player_values`, producing `static_plus_dynamic` broadcasts.
- Preserved the lost-session spell lookup cache and corrected the stale-cache edge: `_spell_preset_lookup()` now checks the current spell directory signature before returning its cached lookup.
- Preserved and verified the magic item registry participation in inventory normalization. Sword of Wounding is now treated as an inventory weapon candidate even though it lives under `Items/Magic_Items/`.

## Code Changes Kept From Lost Session

- LAN `action_id`/`trace_id` acknowledgement and duplicate-action tracking.
- Queue-wait tracing (`queue_wait_ms`, `queue_size`, `slow_queue_wait`).
- Backend/frontend non-clobber handling for partial state updates.
- Static-data backfill from authoritative sources when LAN cache fields are empty.
- Initial `_spell_preset_lookup_cache` / `_spell_preset_lookup_sig` implementation.
- `_normalize_inventory_item_entries()` inclusion of `_magic_items_registry_payload()`.

## Code Changes Added By Codex

- Added explicit `_spell_preset_lookup_cache` initialization and invalidation in spell cache invalidation paths.
- Added `_current_spell_dir_signature()` and changed `_spell_preset_lookup()` to invalidate when spell YAML files change before returning a cached lookup.
- Added a local spell-level cache inside `_normalize_spellbook_runtime_lists()` so repeated cantrip checks do not repeatedly rebuild lookup maps.
- Changed `inventory_equipment_structure` writes so they do not invalidate the global static snapshot cache.
- Extended `_store_character_yaml()` with explicit invalidation, static-refresh, and forced-reload controls.
- Added targeted player-profile projection patching so equip/unequip can update cached `player_profiles` without rebuilding the global spell catalog or monster/static payload.
- Changed inventory/equipment store paths to schedule dynamic-only broadcasts and skip full player YAML cache reloads.
- Added `inventory.equipment.mutation` trace events for item, magic item, weapon assignment, and wearable mutations with profile, item, route, slot/category, YAML load/store timing, invalidation domains, broadcast kind, and changed status.
- Treated Magic_Items entries with `category: weapon` as weapon registry entries even if they are descriptive SRD stubs without `type: weapon` or a `damage` block.
- Added `tests/test_lan_inventory_responsiveness.py`.

## Before / After Profiler Notes

- `_normalize_player_profile`: lost-session profiling reported about 3961ms before the partial cache work. This pass added regression coverage that normalization no longer rebuilds the spell catalog per spell lookup; the focused test allows at most two payload builds for a multi-spell profile rather than one rebuild per spell/cantrip check.
- `_spell_preset_lookup`: before this pass, the lookup cache could stale-return if spell YAML changed before `_spell_presets_payload()` recomputed `_spell_dir_signature`. After this pass, the lookup compares against a freshly computed directory signature and invalidates on spell-file changes.
- `_store_character_yaml`: before this pass, equip/unequip store spans in the provided trace were about 1.9-3.1s and always scheduled broad profile/static refresh behavior. After this pass, inventory/equipment writes use `inventory_equipment_structure`, do not invalidate global static cache, patch only the changed player projection, and schedule dynamic-only broadcast without forced YAML reload.
- Equip/unequip route timing: no live browser smoke was run by Codex. Unit-level trace assertions now verify internal `inventory.equipment.mutation` events with `yaml_load_ms`, `store_yaml_ms`, `invalidation_domains`, and `broadcast_kind`.

## Item Verdicts

- Throat Goat Sword of Wounding: verified equip-eligible from `players/throat_goat.yaml` plus `Items/Magic_Items/sword_of_wounding.yaml`. It appears in normalized owned weapon inventory items with main-hand eligibility.
- Magic weapon attack sync: covered by a focused test proving an equipped magic weapon syncs into `attacks.weapons`.
- Old Man Ring of Greater Invisibility: warning path verified fixed for the narrow case. Inventory item granted pool `ring_of_greater_invisibility` satisfies the magic item spell consume pool, and a truly missing pool still warns.

## Remaining Latency Risks

- First-load and true static/catalog changes can still rebuild large static projections synchronously.
- Startup and full player YAML cache refresh remain expensive outside the ordinary equip/unequip path.
- DM setup actions were not optimized in this pass.
- Browser smoke is still required to confirm user-perceived responsiveness on actual LAN clients.

## Validation

- `./.venv/bin/python3 -m py_compile character_autofill.py combat_service.py combatant_name_service.py dnd_initative_tracker.py helper_script.py map_state.py monster_capability_service.py player_command_contracts.py player_command_service.py runtime_config.py serve_headless.py ship_blueprints.py spell_engine_primitives.py tk_compat.py update_checker.py` passed.
- `./.venv/bin/python3 -m unittest tests.test_items_weapon_resolution` passed: 18 tests.
- `./.venv/bin/python3 -m unittest tests.test_lan_snapshot_cache` passed: 14 tests.
- `./.venv/bin/python3 -m unittest tests.test_lan_snapshot_static` passed: 29 tests.
- `./.venv/bin/python3 -m unittest tests.test_lan_action_safety` passed: 4 tests, with a pre-existing coroutine RuntimeWarning.
- `./.venv/bin/python3 -m unittest tests.test_lan_broadcast_invalidation` passed: 4 tests.
- `./.venv/bin/python3 -m unittest tests.test_lan_movement_action_dispatch` passed: 5 tests.
- `./.venv/bin/python3 -m unittest tests.test_lan_inventory_responsiveness` passed: 13 tests.

## Smoke Recommendation

1. Start headless with debug tracing enabled.
2. Claim Fred, Throat Goat, and Old Man in LAN clients.
3. Equip/unequip Fred bandolier items and verify HTTP requests now emit `inventory.equipment.mutation` with `broadcast_kind=dynamic_only`.
4. Claim Throat Goat and verify Sword of Wounding is equip/weapon-assignment eligible and appears in attack options after equip.
5. Claim Old Man and verify Ring of Greater Invisibility no longer logs unknown `consumes.pool` warnings.
6. During combat, move/end turn/equip/unequip should feel immediate; any action over 1000ms should be inspected in `logs/debug-trace-*.jsonl` by `action_id`.

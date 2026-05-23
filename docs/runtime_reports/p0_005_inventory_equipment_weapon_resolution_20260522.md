# Runtime Report: P0-005 Inventory/Equipment Weapon Resolution

**Date:** 2026-05-22
**Status:** Resolved

## 1. Root Cause
The root cause was two-fold:
1.  **Authoritative Source Disconnect:** Equipped weapons in the `inventory.items` section were not being automatically synced to the `attacks.weapons` list during player profile normalization. This meant that if a player equipped a weapon from their inventory via the LAN UI, it wouldn't show up in their "Attack" options unless it was also explicitly defined in the YAML's `attacks` section.
2.  **Silent Fallback:** The attack resolver in `_adjudicate_attack_request` lacked sufficient tracing and would silently fall back to "Unarmed Strike" if no weapon was matched or found equipped. It also lacked clear user feedback (toasts) explaining why a requested weapon was not being used.

## 2. Source-of-Truth Path
- **Persistent Source:** `players/*.yaml` (specifically `inventory.items` and `attacks.weapons`).
- **Authoritative Loader:** `InitiativeTracker._normalize_player_profile` now correctly syncs equipped items from `inventory` to `attacks.weapons`.

## 3. Payload/Consumer Path
- **Producer:** `InitiativeTracker._player_profiles_payload` builds the profile state for the LAN.
- **Consumer:** LAN frontend (`assets/web/lan/index.html`) uses `getOwnedInventoryWeaponEntries()` which now receives the synced weapons in the `attacks.weapons` list.
- **Persistence:** LAN state updates preserve `player_profiles` during dynamic updates, ensuring inventory data is not lost.

## 4. Attack Resolver Path
- **Entry point:** `PlayerCommandService.attack_request` -> `InitiativeTracker._adjudicate_attack_request`.
- **Resolution priority:**
    1.  User-selected weapon (by ID or name).
    2.  Equipped weapon (marked in `attacks.weapons`, which now includes equipped inventory items).
    3.  First available weapon in the list.
    4.  Unarmed Strike fallback (only if no other options exist and not wild-shaped).

## 5. Fallback Behavior Before/After
- **Before:** Silent fallback to "Unarmed Strike" if weapon matching failed or no weapon was equipped. No indication of failure reason in logs or UI.
- **After:**
    - If a requested weapon is missing, a toast is shown with a clear reason.
    - An oplog warning is logged with a detailed trace of the resolution attempt.
    - Fallback to "Unarmed Strike" only happens if the weapon list is truly empty and no weapon was explicitly requested.
    - Every fallback or successful resolution for John Twilight (or if a fallback occurs) is logged with `fallback_reason` and resolver stages.

## 6. Tests Added
- `test_inventory_payload_non_empty_for_seeded_equipment_user`: Verifies inventory-to-attacks sync.
- `test_equipped_weapon_selected_for_attack`: Verifies priority of equipped weapons.
- `test_configured_weapon_prevents_unarmed_fallback`: Verifies fallback to first weapon over unarmed.
- `test_unarmed_fallback_requires_fallback_reason`: Verifies tracing of fallback reasons.
- `test_attack_resolution_traces_inventory_and_fallback_reason`: Verifies UI feedback for missing weapons.
- `test_lan_state_delta_does_not_clear_inventory_equipment_capabilities`: Verifies persistence of inventory data in LAN payloads.

## 7. Validation Results
- All unit tests in `tests.test_items_weapon_resolution` passed (18 tests).
- All unit tests in `tests.test_lan_snapshot_cache` passed (14 tests).
- Relevant LAN and capability tests passed (43 tests total).
- All edited files compile successfully.

## 8. Manual Smoke Recommendation
- Claim **John Twilight** on the LAN UI.
- Verify that **Hellfire Battleaxe (+2)** appears in the Attack menu.
- Open the Inventory tab and verify items are visible.
- Try making an attack and verify the log says "Hellfire Battleaxe (+2)" and NOT "Unarmed Strike".
- Equip a different weapon from inventory (if available) and verify it becomes the default attack.

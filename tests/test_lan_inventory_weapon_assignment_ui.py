import pathlib
import unittest


class LanInventoryWeaponAssignmentUiTests(unittest.TestCase):
    SOURCE_PATH = pathlib.Path("assets/web/lan/index.html")

    def test_weapon_selector_options_are_instance_id_backed(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function getOwnedInventoryWeaponEntries()", source)
        self.assertIn("const instanceId = String(entry?.instance_id || \"\").trim();", source)
        self.assertIn("value: `${instanceId}|one`", source)
        self.assertIn("value: `${instanceId}|two`", source)

    def test_defaults_derive_from_inventory_equipped_slot_and_selected_mode(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function getEquippedWeaponSelectionsFromInventory(mainhandOptions, offhandOptions)", source)
        self.assertIn("entry?.equipped_slot === \"main_hand\"", source)
        self.assertIn("entry?.equipped_slot === \"off_hand\"", source)
        self.assertIn("const selectedMode = entry?.selected_mode === \"two\" ? \"two\" : \"one\";", source)

    def test_selector_changes_use_inventory_weapon_assignment_routes(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("async function mutateInventoryWeaponAssignment(instanceId, action, extra=null)", source)
        self.assertIn('equip_main_hand: "equip_weapon_mainhand"', source)
        self.assertIn('equip_off_hand: "equip_weapon_offhand"', source)
        self.assertIn('unequip_weapon: "unequip_weapon"', source)
        self.assertIn('set_weapon_mode: "set_weapon_mode"', source)
        self.assertIn('await mutateInventoryWeaponAssignment(parsedNext.instanceId, "set_weapon_mode", {mode: parsedNext.mode});', source)
        self.assertIn('await mutateInventoryWeaponAssignment(parsedNext.instanceId, "equip_off_hand");', source)
        self.assertIn('await mutateInventoryWeaponAssignment(previousParsed.instanceId, "unequip_weapon");', source)

    def test_weapon_selectors_do_not_persist_via_equipment_update(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("equipment_update", source)
        self.assertNotIn("refreshWeaponSelectors(syncEquipment=true)", source)
        self.assertNotIn("sendEquipmentUpdate();", source)
        self.assertIn('mainhandWeaponSelectEl.addEventListener("change", async (event) => {', source)
        self.assertIn('offhandWeaponSelectEl.addEventListener("change", async (event) => {', source)


if __name__ == "__main__":
    unittest.main()

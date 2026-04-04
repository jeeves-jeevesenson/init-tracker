import pathlib
import unittest


class LanInventoryEquippablesUiTests(unittest.TestCase):
    SOURCE_PATH = pathlib.Path("assets/web/lan/index.html")

    def test_non_magic_armor_and_shield_rows_render_from_owned_inventory_entries(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function resolveOwnedInventoryNonMagicEquippable(item)", source)
        self.assertIn("if (resolveOwnedInventoryMagicItem(item)) return null;", source)
        self.assertIn("if (slots.includes(\"armour\"))", source)
        self.assertIn("if (isShieldItem(item))", source)
        self.assertIn('typeChip.textContent = nonMagicEquippable.kind === "shield" ? "Shield" : "Armor";', source)

    def test_non_magic_armor_and_shield_actions_use_instance_id_endpoints(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("pendingNonMagicItemMutations", source)
        self.assertIn("const targetInstanceId = String(instanceId || \"\").trim();", source)
        self.assertIn("/inventory/items/${encodeURIComponent(targetInstanceId)}/${endpoint}", source)
        self.assertIn("await mutateInventoryNonMagicItem(instanceId, isInventoryItemEquipped(item) ? \"unequip\" : \"equip\");", source)

    def test_weapon_selector_refresh_no_longer_sends_equipment_update(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function refreshWeaponSelectors()", source)
        self.assertNotIn("function sendEquipmentUpdate()", source)
        self.assertNotIn('type: "equipment_update"', source)
        self.assertNotIn("if (syncEquipment){", source)
        self.assertNotIn("refreshWeaponSelectors(false);", source)


if __name__ == "__main__":
    unittest.main()

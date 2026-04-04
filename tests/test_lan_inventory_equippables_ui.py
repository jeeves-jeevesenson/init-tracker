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

    def test_weapon_equipment_sync_can_be_skipped_for_inventory_armor_shield_mutations(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function refreshWeaponSelectors(syncEquipment=true)", source)
        self.assertIn("if (syncEquipment){", source)
        self.assertIn("sendEquipmentUpdate();", source)
        self.assertIn("refreshWeaponSelectors(false);", source)


if __name__ == "__main__":
    unittest.main()

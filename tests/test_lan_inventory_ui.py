import pathlib
import unittest


class LanInventoryUiTests(unittest.TestCase):
    SOURCE_PATH = pathlib.Path("assets/web/lan/index.html")

    def test_inventory_layout_includes_bg3_style_slots_and_backpack_list(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn('id="inventoryHeadSelect"', source)
        self.assertIn('id="inventoryCloakSelect"', source)
        self.assertIn('id="inventoryArmourSelect"', source)
        self.assertIn('id="inventoryGlovesSelect"', source)
        self.assertIn('id="inventoryBootsSelect"', source)
        self.assertIn('id="inventoryAmuletSelect"', source)
        self.assertIn('id="inventoryRingOneSelect"', source)
        self.assertIn('id="inventoryRingTwoSelect"', source)
        self.assertIn('id="inventoryItemsList"', source)
        self.assertIn('id="inventoryConsumableSelect"', source)
        self.assertIn('id="inventoryConsumableAddBtn"', source)

    def test_inventory_button_opens_panel_without_toggle_hide(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn('inventoryBtn.addEventListener("click", () => {', source)
        self.assertIn("setInventoryPanelOpen(true);", source)
        self.assertNotIn("setInventoryPanelOpen(!inventoryPanelOpen)", source)
        self.assertIn('id="inventoryModal"', source)
        self.assertIn("inventoryModal.classList.toggle(\"show\", inventoryPanelOpen);", source)

    def test_inventory_defaults_prefer_equipped_items(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function isInventoryItemEquipped(item)", source)
        self.assertNotIn("inventory.equipped", source)
        self.assertNotIn("profile?.magic_items", source)
        self.assertIn("const equippedDefaults = getEquippedInventoryDefaultsBySlot();", source)
        self.assertIn("if (!isInventoryItemEquipped(item)) return;", source)

    def test_inventory_slot_matching_supports_explicit_tags_and_common_armor_names(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("function normalizeInventorySlotTag(value)", source)
        self.assertIn("item?.equip_slot", source)
        self.assertIn('"plate"', source)
        self.assertIn('"mail"', source)
        self.assertIn('"breastplate"', source)
        self.assertIn('"leather"', source)

    def test_consumables_actions_use_claimed_cid_not_active_controlled_unit(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn('send({type: "inventory_adjust_consumable", cid: claimedCid, consumable_id: consumableId, delta: 1});', source)
        self.assertIn('send({type: "use_consumable", cid: claimedCid, consumable_id: consumableId});', source)
        self.assertNotIn('send({type: "inventory_adjust_consumable", cid, consumable_id: consumableId, delta: 1});', source)
        self.assertNotIn('send({type: "use_consumable", cid, consumable_id: consumableId});', source)

    def test_inventory_consumable_controls_send_narrow_messages(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn('type: "inventory_adjust_consumable"', source)
        self.assertIn('type: "use_consumable"', source)
        self.assertIn("function getConsumablesLibrary()", source)

    def test_inventory_non_magic_equippables_use_instance_targeted_routes(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("function mutateInventoryNonMagicItem(instanceId, action)", source)
        self.assertIn('const endpoint = operation === "equip" ? "equip_non_magic" : "unequip_non_magic";', source)
        self.assertIn("await mutateInventoryNonMagicItem(instanceId, isInventoryItemEquipped(item) ? \"unequip\" : \"equip\");", source)
        self.assertIn("refreshWeaponSelectors(false);", source)


if __name__ == "__main__":
    unittest.main()

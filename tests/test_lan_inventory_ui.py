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

    def test_inventory_button_opens_panel_without_toggle_hide(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn('inventoryBtn.addEventListener("click", () => {', source)
        self.assertIn("setInventoryPanelOpen(true);", source)
        self.assertNotIn("setInventoryPanelOpen(!inventoryPanelOpen)", source)


if __name__ == "__main__":
    unittest.main()

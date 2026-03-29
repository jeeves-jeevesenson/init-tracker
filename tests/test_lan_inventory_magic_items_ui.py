import pathlib
import unittest


class LanInventoryMagicItemsUiTests(unittest.TestCase):
    SOURCE_PATH = pathlib.Path("assets/web/lan/index.html")

    def test_magic_item_ui_uses_instance_targeted_mutation_endpoint(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("async function mutateInventoryMagicItem(instanceId, action)", source)
        self.assertIn("/api/characters/${encodeURIComponent(playerName)}/inventory/items/${encodeURIComponent(targetInstanceId)}/${operation}", source)
        self.assertIn("state.player_profiles[playerName] = updatedPlayer;", source)

    def test_magic_item_rows_show_status_and_actions_from_owned_inventory_item(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("const magicMeta = resolveOwnedInventoryMagicItem(item);", source)
        self.assertIn("const instanceId = String(item?.instance_id || \"\").trim();", source)
        self.assertIn('equipBtn.textContent = isInventoryItemEquipped(item) ? "Unequip" : "Equip";', source)
        self.assertIn('attuneBtn.textContent = isInventoryItemAttuned(item) ? "Unattune" : "Attune";', source)
        self.assertIn('reqChip.textContent = "Requires attunement";', source)

    def test_non_attunement_items_do_not_render_attune_button(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("if (ownedMagicItemRequiresAttunement(item))", source)
        self.assertNotIn("profile.magic_items", source)


if __name__ == "__main__":
    unittest.main()

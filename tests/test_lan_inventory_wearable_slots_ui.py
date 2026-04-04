import pathlib
import unittest


class LanInventoryWearableSlotsUiTests(unittest.TestCase):
    SOURCE_PATH = pathlib.Path("assets/web/lan/index.html")

    def test_wearable_slot_options_and_defaults_are_instance_id_backed(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("return String(item?.instance_id || \"\").trim();", source)
        self.assertIn("const equippedSlot = normalizeInventorySlotTag(item?.equipped_slot);", source)
        self.assertIn('ring_one: ""', source)
        self.assertIn('ring_two: ""', source)

    def test_ring_slots_are_independent(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("if (equippedSlot === \"ring_one\" || equippedSlot === \"ring_two\")", source)
        self.assertIn("defaults[equippedSlot] = value;", source)
        self.assertNotIn("equippedDefaults.ring.filter", source)

    def test_selector_changes_call_wearable_mutation_routes_and_refresh_from_payload(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("await mutateInventoryWearable(nextValue, \"equip\", slotKey);", source)
        self.assertIn("await mutateInventoryWearable(previousInstanceId, \"unequip\");", source)
        self.assertIn("updateClaimedPlayerProfileFromMutation(payload, playerName);", source)
        self.assertIn("refreshInventorySlotSelectors();", source)

    def test_magic_items_still_render_attunement_controls(self):
        source = self.SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("ownedMagicItemRequiresAttunement(item)", source)
        self.assertIn("attuneBtn.textContent = isInventoryItemAttuned(item) ? \"Unattune\" : \"Attune\";", source)


if __name__ == "__main__":
    unittest.main()

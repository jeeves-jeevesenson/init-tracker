import unittest
from pathlib import Path

class TestLanFirearmUi(unittest.TestCase):
    def setUp(self):
        self.lan_html_path = Path("assets/web/lan/index.html")
        self.assertTrue(self.lan_html_path.exists())
        self.source = self.lan_html_path.read_text(encoding="utf-8")

    def test_ammo_ui_elements_present(self):
        self.assertIn('id="mainhandAmmoStatus"', self.source)
        self.assertIn('id="mainhandAmmoValue"', self.source)
        self.assertIn('id="mainhandReloadBtn"', self.source)
        self.assertIn('id="offhandAmmoStatus"', self.source)
        self.assertIn('id="offhandAmmoValue"', self.source)
        self.assertIn('id="offhandReloadBtn"', self.source)

    def test_ammo_helper_functions_present(self):
        self.assertIn("function getSelectedMainhandOption()", self.source)
        self.assertIn("function updateWeaponAmmoStatus()", self.source)
        self.assertIn("updateWeaponAmmoStatus();", self.source)

    def test_reload_command_sent(self):
        self.assertIn('type: "reload_weapon"', self.source)
        self.assertIn('item_instance_id: instanceId', self.source)

if __name__ == "__main__":
    unittest.main()

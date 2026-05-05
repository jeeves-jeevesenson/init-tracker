import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil
from dnd_initative_tracker import InitiativeTracker
from helper_script import Combatant
from player_command_service import PlayerCommandService

class TestFirearmReload(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        # Setup mock app
        self.app = InitiativeTracker()
        self.app.host_mode = "headless"
        self.app._lan = MagicMock()
        self.app._oplog = MagicMock()
        
        # Create a temp player YAML
        self.player_name = "ReloadTester"
        self.player_path = Path(self.test_dir) / "ReloadTester.yaml"
        
        self.player_data = {
            "format_version": 2,
            "name": self.player_name,
            "inventory": {
                "items": [
                    {
                        "id": "p45_service_pistol",
                        "instance_id": "pistol_001",
                        "name": ".45 Service Pistol",
                        "ammo_current": 0,
                        "ammo_max": 8,
                        "properties": ["sidearm", "loud", "magazine_8"]
                    },
                    {
                        "id": "longsword",
                        "instance_id": "sword_001",
                        "name": "Longsword"
                    }
                ]
            },
            "attacks": {
                "weapons": [
                    {
                        "id": "p45_service_pistol",
                        "instance_id": "pistol_001",
                        "name": ".45 Service Pistol",
                        "ammo_current": 0,
                        "ammo_max": 8
                    }
                ]
            }
        }
        
        # Mock profile lookup
        self.app._pc_name_for = MagicMock(return_value=self.player_name)
        self.app._resolve_character_path = MagicMock(return_value=self.player_path)
        self.app._load_character_raw = MagicMock(return_value=self.player_data)
        self.app._store_character_yaml = MagicMock()
        
        # Add combatant
        self.cid = 1
        self.c = Combatant(cid=self.cid, name=self.player_name, hp=20, speed=30, 
                           swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
                           movement_mode="normal", move_remaining=30, initiative=10)
        self.app.combatants[self.cid] = self.c
        
        # Service
        self.service = PlayerCommandService(self.app)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_mutate_reload_from_zero(self):
        res = self.app._mutate_owned_inventory_weapon_reload(self.player_name, "pistol_001")
        self.assertTrue(res["ok"])
        self.assertEqual(res["ammo_before"], 0)
        self.assertEqual(res["ammo_after"], 8)
        self.assertEqual(res["ammo_max"], 8)
        
        # Verify persistence call
        self.app._store_character_yaml.assert_called_once()
        saved_raw = self.app._store_character_yaml.call_args[0][1]
        
        # Check inventory
        pistol = next(item for item in saved_raw["inventory"]["items"] if item["instance_id"] == "pistol_001")
        self.assertEqual(pistol["ammo_current"], 8)
        
        # Check attacks sync
        attack_pistol = next(w for w in saved_raw["attacks"]["weapons"] if w["instance_id"] == "pistol_001")
        self.assertEqual(attack_pistol["ammo_current"], 8)

    def test_mutate_reload_from_partial(self):
        self.player_data["inventory"]["items"][0]["ammo_current"] = 3
        res = self.app._mutate_owned_inventory_weapon_reload(self.player_name, "pistol_001")
        self.assertTrue(res["ok"])
        self.assertEqual(res["ammo_before"], 3)
        self.assertEqual(res["ammo_after"], 8)

    def test_mutate_reload_already_full(self):
        self.player_data["inventory"]["items"][0]["ammo_current"] = 8
        res = self.app._mutate_owned_inventory_weapon_reload(self.player_name, "pistol_001")
        self.assertTrue(res["ok"])
        self.assertEqual(res["ammo_before"], 8)
        self.assertEqual(res["ammo_after"], 8)

    def test_mutate_reload_infer_max_from_properties(self):
        # Remove ammo_max but keep magazine_8 property
        del self.player_data["inventory"]["items"][0]["ammo_max"]
        res = self.app._mutate_owned_inventory_weapon_reload(self.player_name, "pistol_001")
        self.assertTrue(res["ok"])
        self.assertEqual(res["ammo_max"], 8)
        self.assertEqual(res["ammo_after"], 8)

    def test_mutate_reload_non_firearm_fails(self):
        res = self.app._mutate_owned_inventory_weapon_reload(self.player_name, "sword_001")
        self.assertFalse(res["ok"])
        self.assertIn("does not have ammunition capacity", res["reason"])

    def test_mutate_reload_missing_item_fails(self):
        res = self.app._mutate_owned_inventory_weapon_reload(self.player_name, "missing_001")
        self.assertFalse(res["ok"])
        self.assertIn("Weapon not found", res["reason"])

    def test_service_reload_weapon_command(self):
        msg = {
            "type": "reload_weapon",
            "item_instance_id": "pistol_001"
        }
        res = self.service.reload_weapon(msg, cid=self.cid, ws_id=101, is_admin=False)
        self.assertTrue(res["ok"])
        self.assertEqual(res["ammo_after"], 8)
        
        # Check toast
        self.app._lan.toast.assert_called_with(101, "Reloaded .45 Service Pistol (8/8).")

    def test_service_reload_already_full_toast(self):
        self.player_data["inventory"]["items"][0]["ammo_current"] = 8
        msg = {
            "type": "reload_weapon",
            "item_instance_id": "pistol_001"
        }
        res = self.service.reload_weapon(msg, cid=self.cid, ws_id=101, is_admin=False)
        self.assertTrue(res["ok"])
        self.app._lan.toast.assert_called_with(101, ".45 Service Pistol is already full.")

if __name__ == "__main__":
    unittest.main()

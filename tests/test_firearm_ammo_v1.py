import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import os
import shutil
import tempfile
import yaml
from dnd_initative_tracker import InitiativeTracker
from helper_script import Combatant

class TestFirearmAmmoV1(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        # Setup mock app
        self.app = InitiativeTracker()
        self.app.host_mode = "headless"
        
        # Mock LAN and other things to avoid crashes
        self.app._lan = MagicMock()
        self.app._oplog = MagicMock()
        
        # Create a temp player YAML
        self.player_name = "Gunslinger"
        self.player_path = Path(self.test_dir) / "Gunslinger.yaml"
        
        self.player_data = {
            "format_version": 2,
            "name": self.player_name,
            "abilities": {"dex": 16},
            "proficiency": {"bonus": 2},
            "vitals": {"max_hp": 20, "current_hp": 20, "speed": {"walk": 30}},
            "attacks": {
                "weapons": [
                    {
                        "id": "p45_service_pistol",
                        "instance_id": "pistol_001",
                        "name": ".45 Service Pistol",
                        "equipped": True,
                        "ammo_current": 8,
                        "ammo_max": 8,
                        "properties": ["sidearm", "loud", "magazine_8"]
                    }
                ]
            },
            "inventory": {
                "items": [
                    {
                        "id": "p45_service_pistol",
                        "instance_id": "pistol_001",
                        "name": ".45 Service Pistol",
                        "equipped": True,
                        "ammo_current": 8,
                        "ammo_max": 8
                    }
                ]
            }
        }
        
        # Mock profile lookup
        self.app._profile_for_player_name = MagicMock(return_value=self.player_data)
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
        
        # Target
        self.target_cid = 2
        self.target = Combatant(cid=self.target_cid, name="Target", hp=20, speed=30,
                                swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
                                movement_mode="normal", move_remaining=30, initiative=5)
        self.app.combatants[self.target_cid] = self.target

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_firearm_attack_decrements_ammo(self):
        msg = {
            "type": "attack_request",
            "cid": self.cid,
            "target_cid": self.target_cid,
            "weapon_id": "p45_service_pistol",
            "hit": True,
            "attack_roll": 15
        }
        
        # Execute attack
        self.app._adjudicate_attack_request(msg, cid=self.cid, ws_id=101, is_admin=False)
        
        # Check ammo in persisted data via _store_character_yaml
        self.app._store_character_yaml.assert_called_once()
        saved_raw = self.app._store_character_yaml.call_args[0][1]
        
        pistol = next(item for item in saved_raw["inventory"]["items"] if item["instance_id"] == "pistol_001")
        self.assertEqual(pistol["ammo_current"], 7)
        
        # Check Loud log
        self.app._oplog.assert_any_call(unittest.mock.ANY, level="info")
        loud_msg = [call.args[0] for call in self.app._oplog.call_args_list if "Loud firearm discharge" in call.args[0]]
        self.assertTrue(len(loud_msg) > 0)

    def test_empty_firearm_blocks_attack(self):
        # Set ammo to 0 in mocked data
        self.player_data["inventory"]["items"][0]["ammo_current"] = 0
        self.player_data["attacks"]["weapons"][0]["ammo_current"] = 0
        
        msg = {
            "type": "attack_request",
            "cid": self.cid,
            "target_cid": self.target_cid,
            "weapon_id": "p45_service_pistol",
            "hit": True,
            "attack_roll": 15
        }
        
        # Execute attack
        self.app._adjudicate_attack_request(msg, cid=self.cid, ws_id=101, is_admin=False)
        
        # Check toast
        self.app._lan.toast.assert_called_with(101, "The .45 Service Pistol is empty! Reload, matey.")
        
        # Check ammo remains 0 (no store call)
        self.app._store_character_yaml.assert_not_called()

    def test_non_firearm_attack_unaffected(self):
        # Add a sword to mocked data
        self.player_data["attacks"]["weapons"].append({"id": "longsword", "name": "Longsword", "equipped": True})
        
        msg = {
            "type": "attack_request",
            "cid": self.cid,
            "target_cid": self.target_cid,
            "weapon_id": "longsword",
            "hit": True,
            "attack_roll": 15
        }
        
        # Execute attack
        self.app._adjudicate_attack_request(msg, cid=self.cid, ws_id=101, is_admin=False)
        
        # Should not toast empty
        for call in self.app._lan.toast.call_args_list:
            self.assertNotIn("is empty", call.args[1])

if __name__ == "__main__":
    unittest.main()

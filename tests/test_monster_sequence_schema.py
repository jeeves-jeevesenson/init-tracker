import unittest
import sys
import os

# Ensure we can import from the root
sys.path.append(os.getcwd())

from monster_capability_service import MonsterCapabilityService

class TestMonsterSequenceSchema(unittest.TestCase):
    def setUp(self):
        self.service = MonsterCapabilityService()

    def test_fixed_children_default(self):
        """Existing list-based composite defaults to fixed_children."""
        cap = {
            "id": "multiattack",
            "name": "Multiattack",
            "type": "action",
            "action_type": "composite",
            "mechanics": {
                "composite": [
                    {"action_id": "bite", "count": 1},
                    {"action_id": "claw", "count": 2}
                ]
            }
        }
        data = {
            "slug": "troll",
            "capabilities": [
                cap,
                {"id": "bite", "name": "Bite", "type": "action", "executable": True},
                {"id": "claw", "name": "Claw", "type": "action", "executable": True}
            ]
        }
        
        original_match = self.service.match_capabilities_for_combatant
        self.service.match_capabilities_for_combatant = lambda c: data
        
        try:
            summary = self.service.summarize_capabilities_for_ui(1, {"name": "Troll 1"})
            multi = next((a for a in summary["groups"]["actions"] if a["id"] == "multiattack"), None)
            
            self.assertIsNotNone(multi)
            self.assertEqual(multi["mechanics"]["sequence_kind"], "fixed_children")
            self.assertNotIn("choose_n", multi["mechanics"])
            
            resolved = multi["mechanics"]["resolved_composite"]
            self.assertEqual(len(resolved), 2)
            self.assertEqual(resolved[0]["action_id"], "bite")
            self.assertEqual(resolved[0]["count"], 1)
        finally:
            self.service.match_capabilities_for_combatant = original_match

    def test_choose_n_parsing(self):
        """Object-based composite supports choose_n and sequence_kind."""
        cap = {
            "id": "multiattack",
            "name": "Multiattack",
            "type": "action",
            "action_type": "composite",
            "mechanics": {
                "composite": {
                    "sequence_kind": "choose_n",
                    "choose_n": 2,
                    "children": [
                        {"action_id": "pistol", "count": 2},
                        {"action_id": "baton", "count": 2}
                    ]
                }
            }
        }
        data = {
            "slug": "constable",
            "capabilities": [
                cap,
                {"id": "pistol", "name": ".45 Pistol", "type": "action", "executable": True},
                {"id": "baton", "name": "Baton", "type": "action", "executable": True}
            ]
        }
        
        original_match = self.service.match_capabilities_for_combatant
        self.service.match_capabilities_for_combatant = lambda c: data
        
        try:
            summary = self.service.summarize_capabilities_for_ui(1, {"name": "Constable 1"})
            multi = next((a for a in summary["groups"]["actions"] if a["id"] == "multiattack"), None)
            
            self.assertIsNotNone(multi)
            self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
            self.assertEqual(multi["mechanics"]["choose_n"], 2)
            
            resolved = multi["mechanics"]["resolved_composite"]
            self.assertEqual(len(resolved), 2)
            self.assertEqual(resolved[0]["action_id"], "pistol")
            self.assertEqual(resolved[0]["count"], 2)
        finally:
            self.service.match_capabilities_for_combatant = original_match

    def test_unknown_sequence_kind_defaults_to_fixed(self):
        """Unknown sequence_kind is normalized to fixed_children."""
        cap = {
            "id": "multiattack",
            "name": "Multiattack",
            "type": "action",
            "action_type": "composite",
            "mechanics": {
                "composite": {
                    "sequence_kind": "weird_variant",
                    "children": [{"action_id": "bite", "count": 1}]
                }
            }
        }
        data = {
            "slug": "weird-monster",
            "capabilities": [
                cap,
                {"id": "bite", "name": "Bite", "type": "action", "executable": True}
            ]
        }
        
        original_match = self.service.match_capabilities_for_combatant
        self.service.match_capabilities_for_combatant = lambda c: data
        
        try:
            summary = self.service.summarize_capabilities_for_ui(1, {"name": "Weird 1"})
            multi = next((a for a in summary["groups"]["actions"] if a["id"] == "multiattack"), None)
            
            self.assertEqual(multi["mechanics"]["sequence_kind"], "fixed_children")
        finally:
            self.service.match_capabilities_for_combatant = original_match

    def test_sibling_sequence_kind_support(self):
        """Supports sequence_kind and choose_n as siblings to composite in mechanics."""
        cap = {
            "id": "multiattack",
            "name": "Multiattack",
            "type": "action",
            "action_type": "composite",
            "mechanics": {
                "composite": [{"action_id": "bite", "count": 1}],
                "sequence_kind": "choose_n",
                "choose_n": 3
            }
        }
        data = {
            "slug": "sibling-test",
            "capabilities": [
                cap,
                {"id": "bite", "name": "Bite", "type": "action", "executable": True}
            ]
        }
        
        original_match = self.service.match_capabilities_for_combatant
        self.service.match_capabilities_for_combatant = lambda c: data
        
        try:
            summary = self.service.summarize_capabilities_for_ui(1, {"name": "Sibling 1"})
            multi = next((a for a in summary["groups"]["actions"] if a["id"] == "multiattack"), None)
            
            self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
            self.assertEqual(multi["mechanics"]["choose_n"], 3)
        finally:
            self.service.match_capabilities_for_combatant = original_match

if __name__ == "__main__":
    unittest.main()

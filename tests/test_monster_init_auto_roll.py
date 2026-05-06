import unittest
from unittest.mock import patch, MagicMock
import types
from combat_service import CombatService

class TestMonsterInitAutoRoll(unittest.TestCase):
    def setUp(self):
        # Build a minimal fake tracker
        self.tracker = types.SimpleNamespace()
        self.tracker.combatants = {}
        self.tracker._next_id = 1
        self.tracker._lock = MagicMock()
        self.tracker._name_role_memory = {}
        
        # Mock tracker methods
        self.tracker._log = MagicMock()
        self.tracker._rebuild_table = MagicMock()
        self.tracker._lan_force_state_broadcast = MagicMock()
        self.tracker._oplog = MagicMock()
        self.tracker._perf_debug_enabled = MagicMock(return_value=False)
        self.tracker._remember_role = MagicMock()
        
        # Mock spec lookup
        self.goblin_spec = types.SimpleNamespace(
            name="Goblin",
            hp=7,
            speed=30,
            dex=14,
            init_mod=2,
            saving_throws={},
            ability_mods={"dex": 2}
        )
        self.tracker._find_monster_spec_by_slug = MagicMock(side_effect=lambda slug: self.goblin_spec if slug == "goblin" else None)
        
        # Mock create combatant
        def _create_monster_spec_combatant(**kwargs):
            cid = self.tracker._next_id
            self.tracker._next_id += 1
            c = types.SimpleNamespace(
                cid=cid,
                name=kwargs.get("name"),
                initiative=kwargs.get("initiative"),
                dex=kwargs.get("dex") or getattr(kwargs.get("monster_spec"), "dex", 10)
            )
            self.tracker.combatants[cid] = c
            return cid
        self.tracker._create_monster_spec_combatant = _create_monster_spec_combatant
        
        self.service = CombatService(self.tracker)

    def test_monster_spawn_rolls_initiative_if_zero(self):
        # If initiative is passed as 0, it should be rolled.
        # Goblin has init_mod 2. Let's mock the roll to be 10.
        with patch("random.randint", return_value=10):
            result = self.service.add_monster_spec_combatants([
                {"name": "Goblin 1", "monster_slug": "goblin", "initiative": 0}
            ])
        
        self.assertTrue(result["ok"])
        cid = result["added"][0]["cid"]
        self.assertEqual(self.tracker.combatants[cid].initiative, 12) # 10 + 2

    def test_monster_spawn_preserves_explicit_initiative(self):
        # If initiative is non-zero, it should be preserved.
        result = self.service.add_monster_spec_combatants([
            {"name": "Goblin 1", "monster_slug": "goblin", "initiative": 15}
        ])
        
        self.assertTrue(result["ok"])
        cid = result["added"][0]["cid"]
        self.assertEqual(self.tracker.combatants[cid].initiative, 15)

    def test_multi_spawn_rolls_independently(self):
        # Each monster should get its own roll.
        # Mock rolls: 10, 5
        with patch("random.randint", side_effect=[10, 5]):
            result = self.service.add_monster_spec_combatants([
                {"name": "Goblin 1", "monster_slug": "goblin", "initiative": 0},
                {"name": "Goblin 2", "monster_slug": "goblin", "initiative": 0}
            ])
        
        self.assertTrue(result["ok"])
        cid1 = result["added"][0]["cid"]
        cid2 = result["added"][1]["cid"]
        self.assertEqual(self.tracker.combatants[cid1].initiative, 12) # 10 + 2
        self.assertEqual(self.tracker.combatants[cid2].initiative, 7)  # 5 + 2

    def test_uses_dex_if_init_mod_missing(self):
        # If init_mod is missing, derive from dex.
        self.goblin_spec.init_mod = None
        self.goblin_spec.dex = 16 # modifier +3
        
        with patch("random.randint", return_value=10):
            result = self.service.add_monster_spec_combatants([
                {"name": "Goblin 1", "monster_slug": "goblin", "initiative": 0}
            ])
        
        self.assertTrue(result["ok"])
        cid = result["added"][0]["cid"]
        self.assertEqual(self.tracker.combatants[cid].initiative, 13) # 10 + 3

if __name__ == "__main__":
    unittest.main()

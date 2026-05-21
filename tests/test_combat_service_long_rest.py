import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod
from combat_service import CombatService

def _make_combatant(cid: int, name: str, *, ac: int, hp: int, ally: bool = False, is_pc: bool = False):
    c = tracker_mod.base.Combatant(
        cid=cid,
        name=name,
        hp=hp,
        speed=30,
        swim_speed=0,
        fly_speed=0,
        burrow_speed=0,
        climb_speed=0,
        movement_mode="normal",
        move_remaining=30,
        initiative=10,
        ally=ally,
        is_pc=is_pc,
    )
    c.ac = ac
    c.max_hp = hp
    c.temp_hp = 0
    c.action_remaining = 0
    c.bonus_action_remaining = 0
    c.reaction_remaining = 0
    c.spell_cast_remaining = 0
    return c

class TestCombatServiceLongRest(unittest.TestCase):
    def setUp(self):
        self.tracker = mock.Mock(spec=tracker_mod.InitiativeTracker)
        self.tracker.combatants = {
            1: _make_combatant(1, "Player 1", ac=15, hp=10, is_pc=True),
            2: _make_combatant(2, "Enemy 1", ac=12, hp=20, is_pc=False),
        }
        self.tracker._role_for_name = mock.Mock(side_effect=lambda name: "pc" if "Player" in name else "enemy")
        self.tracker._pc_name_for = mock.Mock(return_value="Player 1")
        self.tracker._profile_for_player_name = mock.Mock(return_value={
            "name": "Player 1",
            "resources": {"pools": []},
            "spellcasting": {"spell_slots": {}}
        })
        self.tracker._resolve_spell_slot_profile = mock.Mock(return_value=("Player 1", {}))
        self.tracker._rebuild_table = mock.Mock()
        self.tracker._lan_force_state_broadcast = mock.Mock()
        self.tracker._log = mock.Mock()
        
        self.service = CombatService(self.tracker)

    def test_long_rest_players_only(self):
        result = self.service.long_rest(scope="players")
        
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rested"]), 1)
        self.assertEqual(result["rested"][0]["name"], "Player 1")
        
        p1 = self.tracker.combatants[1]
        self.assertEqual(p1.hp, p1.max_hp)
        self.assertEqual(p1.action_remaining, 1)
        self.assertEqual(p1.bonus_action_remaining, 1)
        
        e1 = self.tracker.combatants[2]
        self.assertEqual(e1.hp, 20) # Enemy HP unchanged
        self.assertEqual(e1.action_remaining, 0) # Enemy turn state unchanged

    def test_long_rest_all(self):
        result = self.service.long_rest(scope="all")
        
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rested"]), 2)
        
        p1 = self.tracker.combatants[1]
        e1 = self.tracker.combatants[2]
        self.assertEqual(p1.hp, p1.max_hp)
        self.assertEqual(e1.hp, e1.max_hp)

if __name__ == "__main__":
    unittest.main()

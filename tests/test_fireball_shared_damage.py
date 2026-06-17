import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod
import re

class TestFireballSharedDamage(unittest.TestCase):
    def setUp(self):
        self.tracker = tracker_mod.InitiativeTracker()
        # Mock minimal dependencies for _lan_auto_resolve_cast_aoe
        self.tracker._log = mock.Mock()
        self.tracker._lan_force_state_broadcast = mock.Mock()
        self.tracker._rebuild_table = mock.Mock()
        self.tracker._damage_perf_enabled = mock.Mock(return_value=False)
        self.tracker._lan_sculpt_spells_context = mock.Mock(return_value=(False, 0))
        self.tracker._lan_is_friendly_unit = mock.Mock(return_value=False)
        self.tracker._display_order = mock.Mock(return_value=[])
        self.tracker._pc_name_for = mock.Mock(return_value="Tester")
        self.tracker._profile_for_player_name = mock.Mock(return_value={})
        self.tracker._apply_damage_via_service = mock.Mock(return_value={"hp_after": 0})
        self.tracker._queue_concentration_save = mock.Mock()
        self.tracker._lan_remove_aoe_by_id = mock.Mock()
        self.tracker._canonical_damage_type = mock.Mock(side_effect=lambda x: x)
        self.tracker._adjust_damage_entries_for_target = mock.Mock(side_effect=lambda t, d: {"entries": d, "notes": []})
        self.tracker._target_has_shatter_save_disadvantage = mock.Mock(return_value=False)
        self.tracker._combatant_save_roll_mode = mock.Mock(return_value="normal")
        self.tracker._roll_save_with_mode = mock.Mock(return_value=(10, 10)) # Mock d20 roll
        self.tracker._condition_is_immune_for_target = mock.Mock(return_value=False)

    def test_shared_damage_roll(self):
        # 1. Setup combatants
        c1 = mock.Mock(cid=1, hp=100, saving_throws={"dex": 0}, ability_mods={"dex": 0}, is_pc=False)
        c1.name = "Target 1"
        c2 = mock.Mock(cid=2, hp=100, saving_throws={"dex": 0}, ability_mods={"dex": 0}, is_pc=False)
        c2.name = "Target 2"
        c3 = mock.Mock(cid=3, hp=100, saving_throws={"dex": 0}, ability_mods={"dex": 0}, is_pc=False)
        c3.name = "Target 3"
        self.tracker.combatants = {1: c1, 2: c2, 3: c3}

        # 2. Setup AoE and Preset (Fireball-like)
        aoe = {
            "name": "Fireball",
            "cx": 5.5,
            "cy": 5.5,
            "radius_ft": 20.0,
            "dc": 15,
            "save_type": "dex",
            "damage_type": "fire"
        }
        # To test success/fail consistency, we use the same effect object if possible,
        # but fireball.yaml uses two.
        # IF we want them to share the roll even if they are different objects,
        # we need a more sophisticated cache key.
        dmg_effect = {
            "effect": "damage",
            "dice": "8d6",
            "damage_type": "fire"
        }
        
        preset = {
            "name": "Fireball",
            "automation": "full",
            "mechanics": {
                "sequence": [
                    {
                        "check": {"kind": "saving_throw", "ability": "dex", "dc": 15},
                        "outcomes": {
                            "fail": [dmg_effect],
                            "success": [dict(dmg_effect, multiplier=0.5)]
                        }
                    }
                ]
            }
        }

        # 3. Mock _map_spell_effect_targets to include our targets
        self.tracker._map_spell_effect_targets = mock.Mock(return_value=[1, 2, 3])

        # 4. Mock _roll_save_with_mode to make Target 3 succeed
        def mock_roll_save(target, ability, **kwargs):
            if getattr(target, "name", "") == "Target 3":
                return (20, 20) # Success
            return (1, 1) # Failure
        self.tracker._roll_save_with_mode = mock_roll_save

        # 5. Mock random.randint to ensure different rolls if called multiple times
        # 8d6 roll 1: 8 sixes = 48
        # 8d6 roll 2: 8 ones = 8
        rolls = [6] * 8 + [1] * 8
        with mock.patch("random.randint", side_effect=rolls):
            self.tracker._lan_auto_resolve_cast_aoe(
                aid=1,
                aoe=aoe,
                caster=None,
                spell_slug="fireball",
                spell_id="fireball",
                slot_level=3,
                preset=preset
            )

        # 6. Verify logs
        log_calls = self.tracker._log.call_args_list
        t1_log = log_calls[0][0][0]
        t2_log = log_calls[1][0][0]
        t3_log = log_calls[2][0][0]
        
        print(f"T1 log: {t1_log}")
        print(f"T2 log: {t2_log}")
        print(f"T3 log: {t3_log}")
        
        t1_dmg = int(re.search(r"-> (\d+) damage", t1_log).group(1))
        t2_dmg = int(re.search(r"-> (\d+) damage", t2_log).group(1))
        t3_dmg = int(re.search(r"-> (\d+) damage", t3_log).group(1))
        
        self.assertEqual(t1_dmg, 48)
        self.assertEqual(t2_dmg, 48)
        # If success/fail are shared, T3 should get half of 48 = 24.
        self.assertEqual(t3_dmg, 24, f"Success damage {t3_dmg} is not half of fail damage {t1_dmg}")

if __name__ == "__main__":
    unittest.main()

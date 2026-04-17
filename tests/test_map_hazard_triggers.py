import unittest
from unittest import mock

import dnd_initative_tracker as tracker_mod


def _c(cid, name, hp):
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
        ally=False,
        is_pc=False,
    )
    c.max_hp = hp
    c.move_total = 30
    c.action_remaining = 1
    c.bonus_action_remaining = 1
    c.reaction_remaining = 1
    c.condition_stacks = []
    return c


class MapHazardTriggerTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._rebuild_table = lambda scroll_to_current=True: None
        self.app._lan_force_state_broadcast = lambda *args, **kwargs: None
        self.app._queue_concentration_save = lambda *args, **kwargs: None
        self.app._retarget_current_after_removal = lambda removed, pre_order=None: None
        self.app._remove_combatants_with_lan_cleanup = lambda cids: None
        self.app._append_lan_log = lambda *args, **kwargs: None
        self.app._normalize_token_color = lambda value: "#ff0000"
        self.app._normalize_facing_degrees = lambda value: 0.0
        self.app._enforce_johns_echo_tether = lambda cid: None
        self.app._mount_uses_rider_movement = lambda c: False
        self.app._sneak_handle_hidden_movement = lambda *args, **kwargs: None
        self.app._log = lambda message, cid=None: self.logs.append((cid, str(message)))
        self.app._map_window = None
        self.app._lan_grid_cols = 12
        self.app._lan_grid_rows = 12
        self.app._lan_positions = {1: (5, 5), 2: (0, 1)}
        self.app._lan_obstacles = set()
        self.app._lan_rough_terrain = {}
        self.app._lan_aoes = {}
        self.app._lan_next_aoe_id = 1
        self.app._lan_auras_enabled = True
        self.app._session_bg_images = []
        self.app._session_next_bg_id = 1
        self.app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 12, "rows": 12, "feet_per_square": 5}})
        self.app._next_stack_id = 1
        self.app.in_combat = True
        self.app.round_num = 1
        self.app.turn_num = 1
        self.app.current_cid = 2
        self.app.start_cid = None
        self.app.combatants = {
            1: _c(1, "Caster", 35),
            2: _c(2, "Target", 30),
        }
        self.app.combatants[2].saving_throws = {"dex": 0, "con": 0}
        self.app.combatants[2].ability_mods = {"dex": 0, "con": 0}
        self.app._display_order = lambda: [self.app.combatants[1], self.app.combatants[2]]

    def _set_hazards(self, hazards):
        self.app._map_state = tracker_mod.MapState.from_dict(
            {
                "grid": {"cols": 12, "rows": 12, "feet_per_square": 5},
                "hazards": list(hazards),
            }
        )

    def test_enter_or_end_hazard_dedupes_within_same_turn(self):
        self._set_hazards(
            [
                {
                    "id": "h_fire",
                    "col": 0,
                    "row": 0,
                    "kind": "fire",
                    "payload": {
                        "name": "Deck Fire",
                        "over_time": True,
                        "trigger_on_start_or_enter": "enter_or_end",
                        "dice": "1d6",
                        "damage_type": "fire",
                    },
                }
            ]
        )
        with mock.patch("dnd_initative_tracker.random.randint", return_value=4):
            ok, reason, _cost = self.app._lan_try_move(2, 0, 0)
            self.assertTrue(ok, reason)
            hp_after_enter = self.app.combatants[2].hp
            self.app._end_turn_cleanup(2)
            self.assertEqual(self.app.combatants[2].hp, hp_after_enter)
            self.app.turn_num += 1
            self.app.current_cid = 2
            self.app._end_turn_cleanup(2)
        self.assertLess(self.app.combatants[2].hp, hp_after_enter)

    def test_leave_hazard_triggers_when_unit_moves_out(self):
        self._set_hazards(
            [
                {
                    "id": "h_frost",
                    "col": 0,
                    "row": 0,
                    "kind": "frost",
                    "payload": {
                        "name": "Frost Patch",
                        "over_time": True,
                        "trigger_on_start_or_enter": "leave",
                        "dice": "1d4",
                        "damage_type": "cold",
                    },
                }
            ]
        )
        self.app._lan_positions[2] = (0, 0)
        with mock.patch("dnd_initative_tracker.random.randint", return_value=3):
            ok, reason, _cost = self.app._lan_try_move(2, 0, 1)
        self.assertTrue(ok, reason)
        self.assertEqual(self.app.combatants[2].hp, 27)

    def test_hazard_failed_save_applies_condition(self):
        self._set_hazards(
            [
                {
                    "id": "h_oil",
                    "col": 0,
                    "row": 0,
                    "kind": "grease",
                    "payload": {
                        "name": "Oil Slick",
                        "over_time": True,
                        "trigger_on_start_or_enter": "enter",
                        "save_type": "dex",
                        "dc": 12,
                        "condition_on_fail": "prone",
                        "condition_duration_turns": 1,
                    },
                }
            ]
        )
        with mock.patch("dnd_initative_tracker.random.randint", return_value=3):
            ok, reason, _cost = self.app._lan_try_move(2, 0, 0)
        self.assertTrue(ok, reason)
        conditions = [str(getattr(stack, "ctype", "") or "").strip().lower() for stack in self.app.combatants[2].condition_stacks]
        self.assertIn("prone", conditions)

    def test_canonical_hazard_move_damage_uses_environment_hook(self):
        self._set_hazards(
            [
                {
                    "id": "h_spikes",
                    "col": 0,
                    "row": 0,
                    "kind": "spikes",
                    "payload": {
                        "name": "Spike Field",
                        "move_damage_trigger": {"per_feet": 5, "dice": "1d4", "damage_type": "piercing"},
                    },
                }
            ]
        )
        mover = self.app.combatants[2]
        mover.hp = 30
        with mock.patch("dnd_initative_tracker.random.randint", return_value=2):
            self.app._apply_environmental_move_damage(mover, (0, 1), (0, 0), 10)
        self.assertEqual(mover.hp, 26)

    def test_canonical_hazard_environment_modifiers_apply_to_occupant(self):
        self._set_hazards(
            [
                {
                    "id": "h_smoke",
                    "col": 0,
                    "row": 0,
                    "kind": "smoke",
                    "payload": {
                        "name": "Smoke Cloud",
                        "derived_conditions": [{"condition": "deafened", "requires": "entirely_inside"}],
                        "damage_rules": [{"damage_type": "thunder", "mode": "immunity", "requires": "entirely_inside"}],
                    },
                }
            ]
        )
        self.app._lan_positions[2] = (0, 0)
        mods = self.app._collect_environmental_modifiers_for_combatant(self.app.combatants[2])
        self.assertIn("deafened", mods.get("derived_conditions") or set())
        self.assertIn("thunder", mods.get("damage_immunities") or set())


if __name__ == "__main__":
    unittest.main()

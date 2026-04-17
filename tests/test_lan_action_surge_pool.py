import unittest
from unittest import mock

import dnd_initative_tracker as tracker_mod


class LanActionSurgePoolTests(unittest.TestCase):
    def test_action_surge_use_consumes_pool_and_grants_action(self):
        toasts = []
        logs = []
        consumed = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "John Twilight"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Fighter", "level": 10}]}}
        app._fighter_level_from_profile = lambda profile: 10
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (consumed.append((player_name, pool_id, cost)) or True, "")
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "John Twilight",
                    "action_remaining": 0,
                    "action_total": 1,
                },
            )()
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        app._lan_apply_action(
            {
                "type": "action_surge_use",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 42,
            }
        )

        self.assertEqual(app.combatants[1].action_remaining, 1)
        self.assertEqual(app.combatants[1].action_total, 2)
        self.assertEqual(consumed, [("John Twilight", "action_surge", 1)])
        self.assertIn((42, "Action Surge used: +1 action."), toasts)
        self.assertTrue(any("uses Action Surge and gains 1 action" in message for _cid, message in logs))


    def test_second_wind_use_accepts_manual_healing_roll(self):
        toasts = []
        logs = []
        consumed = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "John Twilight"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Fighter", "level": 10}]}}
        app._fighter_level_from_profile = lambda profile: 10
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (consumed.append((player_name, pool_id, cost)) or True, "")
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app._use_bonus_action = lambda c: True
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "John Twilight",
                    "hp": 20,
                    "max_hp": 60,
                    "bonus_action_remaining": 1,
                },
            )()
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        app._lan_apply_action(
            {
                "type": "second_wind_use",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 42,
                "healing_roll": 7,
            }
        )

        self.assertEqual(app.combatants[1].hp, 37)
        self.assertEqual(consumed, [("John Twilight", "second_wind", 1)])
        self.assertIn((42, "Second Wind: regained 17 HP."), toasts)
        self.assertTrue(any("uses Second Wind and regains 17 HP" in message for _cid, message in logs))

    def test_monk_patient_defense_focus_sets_disengage_and_temp_hp(self):
        toasts = []
        logs = []
        consumed = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "Old Man"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Monk", "level": 10}]}}
        app._class_level_from_profile = lambda profile, klass: 10 if str(klass).lower() == "monk" else 0
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (
            consumed.append((player_name, pool_id, cost)) or True,
            "",
        )
        app._use_bonus_action = lambda c: True
        app._apply_heal_via_service = lambda cid, amount, is_temp_hp=False: setattr(
            app.combatants[int(cid)],
            "temp_hp" if bool(is_temp_hp) else "hp",
            int(amount) if bool(is_temp_hp) else int(getattr(app.combatants[int(cid)], "hp", 0) + int(amount)),
        )
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Old Man",
                    "is_pc": True,
                    "hp": 20,
                    "max_hp": 40,
                    "temp_hp": 3,
                    "bonus_action_remaining": 1,
                },
            )()
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()
        with mock.patch("player_command_service.random.randint", side_effect=[4, 5]):
            app._lan_apply_action(
                {
                    "type": "monk_patient_defense",
                    "cid": 1,
                    "_claimed_cid": 1,
                    "_ws_id": 44,
                    "mode": "focus",
                }
            )

        self.assertEqual(consumed, [("Old Man", "focus_points", 1)])
        self.assertTrue(bool(getattr(app.combatants[1], "disengage_active", False)))
        self.assertEqual(app.combatants[1].temp_hp, 9)
        self.assertIn((44, "Patient Defense used (1 Focus)."), toasts)
        self.assertTrue(any("Patient Defense" in message for _cid, message in logs))

    def test_monk_step_of_wind_focus_consumes_pool_and_adds_movement(self):
        toasts = []
        logs = []
        consumed = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "Old Man"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Monk", "level": 5}]}}
        app._class_level_from_profile = lambda profile, klass: 5 if str(klass).lower() == "monk" else 0
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (
            consumed.append((player_name, pool_id, cost)) or True,
            "",
        )
        app._use_bonus_action = lambda c: True
        app._mode_speed = lambda c: 40
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Old Man",
                    "is_pc": True,
                    "move_total": 30,
                    "move_remaining": 10,
                    "bonus_action_remaining": 1,
                },
            )()
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        app._lan_apply_action(
            {
                "type": "monk_step_of_wind",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 45,
                "mode": "focus",
            }
        )

        self.assertEqual(consumed, [("Old Man", "focus_points", 1)])
        self.assertEqual(app.combatants[1].move_total, 70)
        self.assertEqual(app.combatants[1].move_remaining, 50)
        self.assertIn((45, "Step of the Wind used."), toasts)
        self.assertTrue(any("Step of the Wind" in message for _cid, message in logs))

    def test_monk_elemental_attunement_activate_then_deactivate(self):
        toasts = []
        consumed = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "Old Man"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Monk", "level": 10}]}}
        app._class_level_from_profile = lambda profile, klass: 10 if str(klass).lower() == "monk" else 0
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (
            consumed.append((player_name, pool_id, cost)) or True,
            "",
        )
        app._elemental_attunement_active = lambda c: bool(getattr(c, "elemental_attunement_active", False))
        app._log = lambda *args, **kwargs: None
        app._rebuild_table = lambda scroll_to_current=True: None
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Old Man",
                    "is_pc": True,
                    "elemental_attunement_active": False,
                },
            )()
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        app._lan_apply_action({"type": "monk_elemental_attunement", "cid": 1, "_claimed_cid": 1, "_ws_id": 46})
        app._lan_apply_action(
            {
                "type": "monk_elemental_attunement",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 46,
                "mode": "deactivate",
            }
        )

        self.assertEqual(consumed, [("Old Man", "focus_points", 1)])
        self.assertFalse(bool(getattr(app.combatants[1], "elemental_attunement_active", False)))
        self.assertIn((46, "Elemental Attunement activated."), toasts)
        self.assertIn((46, "Elemental Attunement ended."), toasts)


    def test_lay_on_hands_use_consumes_pool_spends_action_and_heals_target(self):
        toasts = []
        logs = []
        consumed = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "Dorian"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Paladin", "level": 10}]}}
        app._class_level_from_profile = lambda profile, klass: 10 if str(klass).lower() == "paladin" else 0
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (consumed.append((player_name, pool_id, cost)) or True, "")
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app._use_action = lambda c: True
        app._use_bonus_action = lambda c: True
        app._refresh_monster_phase_for_combatant = lambda *a, **kw: None
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Dorian", "action_remaining": 1, "bonus_action_remaining": 1, "hp": 40, "max_hp": 102})(),
            2: type("T", (), {"cid": 2, "name": "Ally", "hp": 10, "max_hp": 60})(),
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        app._lan_apply_action(
            {
                "type": "lay_on_hands_use",
                "cid": 1,
                "target_cid": 2,
                "amount": 25,
                "_claimed_cid": 1,
                "_ws_id": 42,
            }
        )

        self.assertEqual(app.combatants[2].hp, 35)
        self.assertEqual(consumed, [("Dorian", "lay_on_hands", 25)])
        self.assertIn((42, "Lay on Hands: healed 25 HP."), toasts)
        self.assertTrue(any("uses Lay on Hands on Ally" in message for _cid, message in logs))

    def test_lay_on_hands_cure_poisoned_path_spends_pool_without_heal_toast(self):
        toasts = []
        logs = []
        consumed = []
        cleared_conditions = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "Dorian"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Paladin", "level": 10}]}}
        app._class_level_from_profile = lambda profile, klass: 10 if str(klass).lower() == "paladin" else 0
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (consumed.append((player_name, pool_id, cost)) or True, "")
        app._remove_condition_type = lambda target, condition: cleared_conditions.append((int(target.cid), condition))
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app._use_bonus_action = lambda c: True
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Dorian", "bonus_action_remaining": 1})(),
            2: type("T", (), {"cid": 2, "name": "Ally", "hp": 10, "max_hp": 60})(),
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        app._lan_apply_action(
            {
                "type": "lay_on_hands_use",
                "cid": 1,
                "target_cid": 2,
                "cure_poisoned": True,
                "_claimed_cid": 1,
                "_ws_id": 43,
            }
        )

        self.assertEqual(consumed, [("Dorian", "lay_on_hands", 5)])
        self.assertEqual(cleared_conditions, [(2, "poisoned")])
        self.assertIn((43, "Lay on Hands: removed Poisoned."), toasts)
        self.assertFalse(any(message == "Lay on Hands: healed 0 HP." for _ws_id, message in toasts))
        self.assertTrue(any("remove Poisoned" in message for _cid, message in logs))

    def test_monk_uncanny_metabolism_refills_focus_and_heals(self):
        toasts = []
        logs = []
        consumed = []
        focused = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._pc_name_for = lambda cid: "Old Man"
        app._profile_for_player_name = lambda name: {
            "leveling": {"classes": [{"name": "Monk", "level": 10}]},
            "resources": {"pools": [{"id": "focus_points", "current": 2, "max": 10}]},
        }
        app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (
            consumed.append((player_name, pool_id, cost)) or True,
            "",
        )
        app._set_player_resource_pool_current = lambda player_name, pool_id, current: (
            focused.append((player_name, pool_id, current)) or True,
            "",
        )
        app._log = lambda message, cid=None: logs.append((cid, message))
        app._rebuild_table = lambda scroll_to_current=True: None
        app._use_bonus_action = lambda c: True
        app._refresh_monster_phase_for_combatant = lambda *a, **kw: None
        app.in_combat = True
        app.current_cid = 1
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Old Man",
                    "is_pc": True,
                    "hp": 20,
                    "max_hp": 40,
                    "bonus_action_remaining": 1,
                },
            )()
        }
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        with mock.patch("dnd_initative_tracker.random.randint", return_value=6):
            app._lan_apply_action(
                {
                    "type": "monk_uncanny_metabolism",
                    "cid": 1,
                    "_claimed_cid": 1,
                    "_ws_id": 42,
                }
            )

        self.assertEqual(consumed, [("Old Man", "uncanny_metabolism", 1)])
        self.assertEqual(focused, [("Old Man", "focus_points", 10)])
        self.assertEqual(app.combatants[1].hp, 26)
        self.assertIn((42, "Uncanny Metabolism used."), toasts)
        self.assertTrue(any("used Uncanny Metabolism" in message for _cid, message in logs))


if __name__ == "__main__":
    unittest.main()

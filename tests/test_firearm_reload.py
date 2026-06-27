import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil
from dnd_initative_tracker import InitiativeTracker
from helper_script import Combatant
from monster_capability_service import MonsterCapabilityService
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

    def _make_monster_actor(self, cid, name, slug):
        actor = Combatant(
            cid=cid, name=name, hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        actor.is_pc = False
        actor.monster_slug = slug
        self.app.combatants[cid] = actor
        return actor

    def _make_target_actor(self, cid, name="Target"):
        target = Combatant(
            cid=cid, name=name, hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=5
        )
        self.app.combatants[cid] = target
        return target

    def _configure_monster_capability_testbed(self):
        svc = MonsterCapabilityService()
        self.app._ensure_monster_capabilities = MagicMock(return_value=svc)
        self.app._monster_modifier_state = {}
        self.app._monster_sequence_state = {}
        self.app._lan_force_state_broadcast = MagicMock()
        self.app._rebuild_table = MagicMock()
        self.app._apply_map_attack_manual_damage = MagicMock(return_value={"ok": True})
        self.app._dm_monster_capability_effect_change = MagicMock(return_value={"ok": True})
        self.app._lan_positions = {}
        self.app.round_num = 1
        self.app.turn_num = 1
        return svc

    def _seed_monster_capability_ammo(self, actor, capability_id, current=None):
        svc = self.app._ensure_monster_capabilities()
        cap = next(
            c for c in svc.match_capabilities_for_combatant(actor)["capabilities"]
            if c["id"] == capability_id
        )
        self.app._monster_capability_ensure_resource_state(actor.cid, cap)
        if current is not None:
            self.app._monster_resource_state[f"{actor.cid}:ammo:{capability_id}:current"] = int(current)
        return cap

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

    def test_lan_apply_action_routes_reload_weapon(self):
        msg = {
            "type": "reload_weapon",
            "item_instance_id": "pistol_001",
            "cid": self.cid,
            "_claimed_cid": self.cid,
            "_ws_id": 101,
        }
        with patch.object(self.service, "reload_weapon", return_value={"ok": True, "ammo_after": 8}) as mock_reload:
            self.app.in_combat = False
            self.app._player_commands = self.service
            self.app._lan_apply_action(msg)
            mock_reload.assert_called_once_with(msg, cid=self.cid, ws_id=101, is_admin=False)

    def test_dm_monster_capability_reload_resource_op(self):
        monster_cid = 2
        monster_actor = Combatant(
            cid=monster_cid, name="Rifleman 1", hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        monster_actor.is_pc = False
        monster_actor.monster_slug = "black-and-tan-rifleman"

        self.app.combatants[monster_cid] = monster_actor
        self.app.in_combat = False
        self.app._monster_resource_state = {}

        from monster_capability_service import MonsterCapabilityService
        svc = MonsterCapabilityService()
        self.app._ensure_monster_capabilities = MagicMock(return_value=svc)

        self.app._monster_resource_state[f"{monster_cid}:ammo:armalite-rifle:current"] = 10
        self.app._monster_resource_state[f"{monster_cid}:ammo:armalite-rifle:max"] = 20
        self.app._monster_resource_state[f"{monster_cid}:ammo:5.56:reserve_mags"] = 3

        payload = {
            "capability_id": "armalite-rifle",
            "operation": "reload"
        }
        res = self.app._dm_monster_capability_resource_op(cid=monster_cid, payload=payload)

        self.assertTrue(res["ok"])
        self.assertEqual(res["new_value"], 20)
        self.assertEqual(self.app._monster_resource_state[f"{monster_cid}:ammo:armalite-rifle:current"], 20)
        self.assertEqual(self.app._monster_resource_state[f"{monster_cid}:ammo:5.56:reserve_mags"], 2)

    def test_dm_capability_reload_rolls_back_when_spend_fails(self):
        actor_cid = 3
        actor = Combatant(
            cid=actor_cid, name="Spend Checked Actor", hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        actor.is_pc = True
        actor.action_remaining = 0
        self.app.combatants[actor_cid] = actor
        self.app._monster_resource_state = {
            f"{actor_cid}:ammo:test-rifle:current": 1,
            f"{actor_cid}:ammo:5.56:reserve_mags": 2,
        }

        svc = MagicMock()
        svc.match_capabilities_for_combatant.return_value = {
            "capabilities": [
                {
                    "id": "test-rifle",
                    "name": "Test Rifle",
                    "mechanics": {
                        "magazine_capacity": 20,
                        "ammo_type": "5.56",
                        "reload_cost": "action",
                    },
                }
            ]
        }
        self.app._ensure_monster_capabilities = MagicMock(return_value=svc)

        res = self.app._dm_monster_capability_resource_op(
            cid=actor_cid,
            payload={"capability_id": "test-rifle", "operation": "reload"},
        )

        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "No actions left, matey.")
        self.assertEqual(self.app._monster_resource_state[f"{actor_cid}:ammo:test-rifle:current"], 1)
        self.assertEqual(self.app._monster_resource_state[f"{actor_cid}:ammo:5.56:reserve_mags"], 2)

    def test_dm_summary_filters_placeholder_reload_without_reloadable_weapon(self):
        actor_cid = 4
        actor = Combatant(
            cid=actor_cid, name="Knife Raider", hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        actor.is_pc = False
        actor.monster_slug = "knife-raider"
        self.app.combatants[actor_cid] = actor

        reload_cap = {
            "id": "reload",
            "name": "Reload",
            "type": "bonus_action",
            "executable": True,
            "action_type": "firearm_reload",
            "mechanics": {"firearm_reload": True},
        }
        knife_cap = {
            "id": "knife",
            "name": "Knife",
            "type": "action",
            "executable": True,
            "action_type": "melee_attack",
            "mechanics": {"attack_bonus": 4},
        }
        svc = MagicMock()
        svc.match_capabilities_for_combatant.return_value = {
            "slug": "knife-raider",
            "capabilities": [reload_cap, knife_cap],
        }
        svc.summarize_capabilities_for_ui.return_value = {
            "matched": True,
            "combatant_id": actor_cid,
            "slug": "knife-raider",
            "name": actor.name,
            "groups": {
                "actions": [knife_cap],
                "bonus_actions": [reload_cap],
                "reactions": [],
                "legendary_actions": [],
                "traits": [],
                "lair_actions": [],
                "special": [],
            },
        }
        self.app._ensure_monster_capabilities = MagicMock(return_value=svc)

        summary = self.app._dm_monster_capability_summary_for_ui(actor_cid, actor)

        self.assertEqual(summary["groups"]["bonus_actions"], [])

    def test_dm_summary_labels_reload_targets_for_multiple_weapons(self):
        actor_cid = 5
        actor = Combatant(
            cid=actor_cid, name="Rifleman 2", hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        actor.is_pc = False
        actor.monster_slug = "black-and-tan-rifleman"
        self.app.combatants[actor_cid] = actor
        self.app._ensure_monster_capabilities = MagicMock(return_value=MonsterCapabilityService())

        summary = self.app._dm_monster_capability_summary_for_ui(actor_cid, actor)
        reload_cap = next(cap for cap in summary["groups"]["bonus_actions"] if cap["id"] == "reload")

        self.assertTrue(reload_cap["reload_selection_required"])
        self.assertEqual(reload_cap["reload_target_count"], 2)
        self.assertEqual(reload_cap["mechanics_summary"], "Choose weapon to reload.")
        self.assertEqual(
            [entry["weapon_name"] for entry in reload_cap["reload_targets"]],
            ["Armalite Rifle", ".45 Pistol"],
        )

    def test_dm_monster_reload_action_targets_specific_weapon(self):
        monster_cid = 6
        monster_actor = Combatant(
            cid=monster_cid, name="Rifleman 3", hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        monster_actor.is_pc = False
        monster_actor.monster_slug = "black-and-tan-rifleman"
        self.app.combatants[monster_cid] = monster_actor
        self.app._ensure_monster_capabilities = MagicMock(return_value=MonsterCapabilityService())
        self.app._monster_resource_state = {
            f"{monster_cid}:ammo:armalite-rifle:current": 10,
            f"{monster_cid}:ammo:armalite-rifle:max": 20,
            f"{monster_cid}:ammo:5.56:reserve_mags": 3,
            f"{monster_cid}:ammo:pistol:current": 2,
            f"{monster_cid}:ammo:pistol:max": 8,
            f"{monster_cid}:ammo:.45:reserve_mags": 4,
        }

        res = self.app._dm_monster_capability_resource_op(
            cid=monster_cid,
            payload={"capability_id": "reload", "operation": "reload", "reload_capability_id": "pistol"},
        )

        self.assertTrue(res["ok"])
        self.assertEqual(res["capability_id"], "pistol")
        self.assertEqual(self.app._monster_resource_state[f"{monster_cid}:ammo:pistol:current"], 8)
        self.assertEqual(self.app._monster_resource_state[f"{monster_cid}:ammo:.45:reserve_mags"], 3)
        self.assertEqual(self.app._monster_resource_state[f"{monster_cid}:ammo:armalite-rifle:current"], 10)

    def test_dm_monster_reload_is_blocked_during_active_multiattack(self):
        actor_cid = 7
        actor = Combatant(
            cid=actor_cid, name="Constable 2", hp=20, speed=30,
            swim_speed=0, fly_speed=0, burrow_speed=0, climb_speed=0,
            movement_mode="normal", move_remaining=30, initiative=10
        )
        actor.is_pc = False
        actor.monster_slug = "black-and-tan-constable"
        self.app.combatants[actor_cid] = actor
        self.app.round_num = 3
        self.app.turn_num = 9
        self.app._monster_sequence_state = {
            actor_cid: {
                "parent_capability_id": "multiattack",
                "sequence_kind": "choose_n",
                "choose_n": 2,
                "children": {"pistol": {"completed": 1, "max": 2}},
                "turn_marker": (3, 9),
            }
        }
        self.app._ensure_monster_capabilities = MagicMock(return_value=MonsterCapabilityService())

        res = self.app._dm_monster_capability_resource_op(
            cid=actor_cid,
            payload={"capability_id": "reload", "operation": "reload", "reload_capability_id": "pistol"},
        )

        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "Finish or cancel Multiattack before reloading.")

    def test_dm_monster_attack_preview_does_not_decrement_ammo(self):
        actor = self._make_monster_actor(8, "Preview Rifleman", "black-and-tan-rifleman")
        target = self._make_target_actor(9)
        self._configure_monster_capability_testbed()
        self.app._resolve_map_attack_sequence = MagicMock(return_value={"ok": True})
        self._seed_monster_capability_ammo(actor, "armalite-rifle", current=20)

        res = self.app._dm_monster_capability_execute(
            actor_cid=actor.cid,
            payload={"capability_id": "armalite-rifle", "target_cid": target.cid, "spend": "none"},
        )

        self.assertTrue(res["ok"])
        self.assertEqual(res["resolution"], "assisted")
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:armalite-rifle:current"], 20)

    def test_dm_monster_single_rifle_apply_decrements_ammo_and_summary(self):
        actor = self._make_monster_actor(10, "Rifleman Apply", "black-and-tan-rifleman")
        target = self._make_target_actor(11)
        self._configure_monster_capability_testbed()
        self._seed_monster_capability_ammo(actor, "armalite-rifle", current=20)

        res = self.app._dm_monster_capability_resolve_targets(
            actor_cid=actor.cid,
            payload={
                "capability_id": "armalite-rifle",
                "targets": [{"target_cid": target.cid, "outcome": "fail"}],
                "apply_damage": True,
                "apply_effects": True,
                "spend": "action",
            },
        )

        self.assertTrue(res["ok"])
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:armalite-rifle:current"], 19)
        summary = self.app._dm_monster_capability_summary_for_ui(actor.cid, actor)
        rifle_cap = next(cap for cap in summary["groups"]["actions"] if cap["id"] == "armalite-rifle")
        self.assertEqual(rifle_cap["ammo"]["current"], 19)

    def test_dm_monster_multiattack_rifle_component_decrements_correct_weapon(self):
        actor = self._make_monster_actor(12, "Rifleman Sequence", "black-and-tan-rifleman")
        target = self._make_target_actor(13)
        self._configure_monster_capability_testbed()
        self._seed_monster_capability_ammo(actor, "armalite-rifle", current=20)
        self._seed_monster_capability_ammo(actor, "pistol", current=8)

        start = self.app._dm_monster_capability_execute(actor_cid=actor.cid, payload={"capability_id": "multiattack"})
        self.assertTrue(start["ok"])

        res = self.app._dm_monster_capability_resolve_targets(
            actor_cid=actor.cid,
            payload={
                "capability_id": "armalite-rifle",
                "targets": [{"target_cid": target.cid, "outcome": "fail"}],
                "apply_damage": True,
                "apply_effects": True,
                "spend": "action",
            },
        )

        self.assertTrue(res["ok"])
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:armalite-rifle:current"], 19)
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:pistol:current"], 8)
        self.assertEqual(self.app._monster_sequence_state[actor.cid]["children"]["armalite-rifle"]["completed"], 1)

    def test_dm_monster_failed_apply_does_not_decrement_ammo(self):
        actor = self._make_monster_actor(14, "Rifleman Failure", "black-and-tan-rifleman")
        target = self._make_target_actor(15)
        self._configure_monster_capability_testbed()
        self.app._apply_map_attack_manual_damage = MagicMock(return_value={"ok": False, "error": "simulated failure"})
        self._seed_monster_capability_ammo(actor, "armalite-rifle", current=20)

        res = self.app._dm_monster_capability_resolve_targets(
            actor_cid=actor.cid,
            payload={
                "capability_id": "armalite-rifle",
                "targets": [{"target_cid": target.cid, "outcome": "fail"}],
                "apply_damage": True,
                "apply_effects": True,
                "spend": "action",
            },
        )

        self.assertTrue(res["ok"])
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:armalite-rifle:current"], 20)
        self.assertEqual(res["results"][0]["error"], "simulated failure")

    def test_dm_monster_reload_refills_selected_weapon_after_spend(self):
        actor = self._make_monster_actor(16, "Rifleman Reload", "black-and-tan-rifleman")
        target = self._make_target_actor(17)
        self._configure_monster_capability_testbed()
        self._seed_monster_capability_ammo(actor, "armalite-rifle", current=20)
        self._seed_monster_capability_ammo(actor, "pistol", current=8)

        spend = self.app._dm_monster_capability_resolve_targets(
            actor_cid=actor.cid,
            payload={
                "capability_id": "pistol",
                "targets": [{"target_cid": target.cid, "outcome": "fail"}],
                "apply_damage": True,
                "apply_effects": True,
                "spend": "action",
            },
        )
        self.assertTrue(spend["ok"])
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:pistol:current"], 7)

        reload_res = self.app._dm_monster_capability_resource_op(
            cid=actor.cid,
            payload={"capability_id": "reload", "operation": "reload", "reload_capability_id": "pistol"},
        )

        self.assertTrue(reload_res["ok"])
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:pistol:current"], 8)
        self.assertEqual(self.app._monster_resource_state[f"{actor.cid}:ammo:armalite-rifle:current"], 20)

if __name__ == "__main__":
    unittest.main()

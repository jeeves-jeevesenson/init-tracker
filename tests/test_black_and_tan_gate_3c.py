import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestBlackAndTanGate3C(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="black-and-tan-shield-trooper", is_pc=False, name="Shield 1", reaction_remaining=1),
                2: mock.Mock(cid=2, monster_slug="black-and-tan-rifleman", is_pc=False, name="Rifleman 2", reaction_remaining=1, hp=30, max_hp=30, temp_hp=0),
                3: mock.Mock(cid=3, monster_slug="black-and-tan-field-medic", is_pc=False, name="Medic 3", reaction_remaining=1),
                4: mock.Mock(cid=4, monster_slug="black-and-tan-captain", is_pc=False, name="Captain 4", reaction_remaining=1, hp=40, max_hp=145, temp_hp=0),
                5: mock.Mock(cid=5, is_pc=True, name="Hero", hp=100),
            },
            "_monster_resource_state": {},
            "_monster_modifier_state": {},
            "_monster_sequence_state": {},
            "_pending_prompts": {},
            "_name_role_memory": {
                "Shield 1": "enemy",
                "Rifleman 2": "enemy",
                "Medic 3": "enemy",
                "Captain 4": "enemy",
                "Hero": "pc"
            },
            "active_cid": 5,
            "round_num": 1,
            "turn_num": 1,
            "in_combat": True
        })
        
        # Mocking methods
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._lan_force_state_broadcast = lambda: None
        self.app._log = lambda *args, **kwargs: None
        self.app._oplog = lambda *args, **kwargs: None
        self.app._lan_feet_per_square = lambda: 5.0
        self.app._combatant_distance_ft = lambda source, target: 5.0 # Adjacent
        self.app._combatants_are_hostile = lambda source, target: (
            (getattr(source, "name") == "Hero" and getattr(target, "name") != "Hero") or
            (getattr(source, "name") != "Hero" and getattr(target, "name") == "Hero")
        )
        self.app._pc_name_for = lambda cid: "Hero" if cid == 5 else None
        self.app._profile_for_player_name = lambda name: {} if name == "Hero" else None
        self.app._use_reaction = tracker_mod.InitiativeTracker._use_reaction.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._monster_capability_can_react = tracker_mod.InitiativeTracker._monster_capability_can_react.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._create_monster_prompt = tracker_mod.InitiativeTracker._create_monster_prompt.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._trigger_monster_hit_reaction_prompts = tracker_mod.InitiativeTracker._trigger_monster_hit_reaction_prompts.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._trigger_monster_death_reaction_prompts = tracker_mod.InitiativeTracker._trigger_monster_death_reaction_prompts.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._build_monster_prompt_result = tracker_mod.InitiativeTracker._build_monster_prompt_result.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._resolve_monster_prompt = tracker_mod.InitiativeTracker._resolve_monster_prompt.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._execute_monster_reaction = tracker_mod.InitiativeTracker._execute_monster_reaction.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._resume_monster_prompt_resolution = tracker_mod.InitiativeTracker._resume_monster_prompt_resolution.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._is_black_and_tan = tracker_mod.InitiativeTracker._is_black_and_tan.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._is_black_and_tan_officer = tracker_mod.InitiativeTracker._is_black_and_tan_officer.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._resolved_monster_capabilities_for_target = tracker_mod.InitiativeTracker._resolved_monster_capabilities_for_target.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._append_resolved_monster_capability = tracker_mod.InitiativeTracker._append_resolved_monster_capability.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._normalize_cid_value = tracker_mod._normalize_cid_value
        self.app._normalize_monster_save_result = tracker_mod.InitiativeTracker._normalize_monster_save_result.__get__(self.app, tracker_mod.InitiativeTracker)

        tracker_mod.apply_resume_dispatch = lambda x: x.get("payload") if isinstance(x, dict) else None

        # Mock player commands prompts
        self.prompts_store = {}
        def mock_create_reaction_offer(**kwargs):
            prompt_id = kwargs.get("prompt_id")
            reactor_cid = int(kwargs.get("reactor_cid") or -1)
            prompt = dict(kwargs)
            prompt["metadata"] = kwargs.get("extra_payload", {})
            prompt["resume"] = kwargs.get("resume_dispatch", {})
            if reactor_cid in self.app.combatants:
                prompt["reactor_name"] = self.app.combatants[reactor_cid].name
            self.prompts_store[prompt_id] = prompt
            return prompt_id
        
        prompts = mock.Mock()
        prompts.create_reaction_offer.side_effect = mock_create_reaction_offer
        prompts.get_prompt.side_effect = lambda pid: self.prompts_store.get(pid)
        prompts.pop_prompt.side_effect = lambda pid: self.prompts_store.pop(pid, None)
        
        player_service = mock.Mock()
        player_service.prompts = prompts
        self.app._ensure_player_commands = lambda: player_service

    def test_interpose_shield_trigger_and_resolve(self):
        # Rifleman 2 is hit by Hero
        damage_entries = [{"amount": 15, "type": "piercing"}]
        resume_dispatch = {
            "command_type": "attack_request",
            "actor_cid": 5,
            "payload": {"hit": True}
        }
        prompt_id = self.app._trigger_monster_hit_reaction_prompts(
            target_cid=2,
            attacker_cid=5,
            damage_entries=damage_entries,
            resume_dispatch=resume_dispatch
        )
        
        self.assertIsNotNone(prompt_id)
        self.assertIn(prompt_id, self.prompts_store)
        prompt = self.prompts_store[prompt_id]
        self.assertEqual(prompt["reactor_cid"], 1) # Shield Trooper
        self.assertEqual(prompt["extra_payload"]["capability_id"], "interpose-shield")
        
        # Resolve prompt with "use"
        with mock.patch.object(self.app, "_adjudicate_attack_request") as mock_resume:
            resolved = self.app._resolve_monster_prompt(prompt_id, "use")
            if not resolved.get("ok"):
                print(f"DEBUG RESOLVED FAIL: {resolved}")
            
            self.assertTrue(resolved["ok"])
            self.assertEqual(self.app.combatants[1].reaction_remaining, 0)
            self.assertEqual(resolved["final_result"]["reduction"], 10)
            self.assertEqual(resolved["final_result"]["damage_entries"][0]["amount"], 5)
            
            # Verify resume
            mock_resume.assert_called_once()
            res_payload = mock_resume.call_args[0][0]
            self.assertEqual(res_payload["_monster_forced_damage_entries"][0]["amount"], 5)
            self.assertTrue(res_payload["_interception_resolution_done"])

    def test_keep_officer_breathing_trigger_and_resolve(self):
        # Captain 4 (Officer) would drop to 0
        resume_dispatch = {
            "command_type": "attack_request",
            "actor_cid": 5,
            "payload": {"hit": True}
        }
        prompt_id = self.app._trigger_monster_death_reaction_prompts(
            target_cid=4,
            attacker_cid=5,
            resume_dispatch=resume_dispatch
        )
        
        self.assertIsNotNone(prompt_id)
        self.assertIn(prompt_id, self.prompts_store)
        prompt = self.prompts_store[prompt_id]
        self.assertEqual(prompt["reactor_cid"], 3) # Medic
        self.assertEqual(prompt["extra_payload"]["capability_id"], "keep-officer-breathing")
        
        # Resolve prompt with "use"
        with mock.patch.object(self.app, "_adjudicate_attack_request") as mock_resume:
            resolved = self.app._resolve_monster_prompt(prompt_id, "use")
            if not resolved.get("ok"):
                print(f"DEBUG RESOLVED FAIL: {resolved}")
            
            self.assertTrue(resolved["ok"])
            self.assertEqual(self.app.combatants[3].reaction_remaining, 0)
            self.assertEqual(resolved["final_result"]["set_hp_to"], 1)
            
            # Verify resume
            mock_resume.assert_called_once()
            res_payload = mock_resume.call_args[0][0]
            self.assertEqual(res_payload["_monster_forced_hp_after"], 1)
            self.assertTrue(res_payload["_keep_officer_breathing_done"])

if __name__ == "__main__":
    unittest.main()

import copy
import unittest
from unittest import mock

import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService


class TestReactionPromptAutomation(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update(
            {
                "combatants": {
                    1: mock.Mock(cid=1, monster_slug="black-and-tan-suppression-gunner", is_pc=False, name="Gunner", reaction_remaining=1),
                    2: mock.Mock(cid=2, monster_slug="black-and-tan-captain", is_pc=False, name="Captain", reaction_remaining=1, hp=40, max_hp=40),
                    3: mock.Mock(cid=3, monster_slug="black-and-tan-major", is_pc=False, name="Major", reaction_remaining=1, hp=50, max_hp=50),
                    4: mock.Mock(cid=4, monster_slug="black-and-tan-rifleman", is_pc=False, name="Rifleman", reaction_remaining=1, hp=30, max_hp=30),
                },
                "_monster_resource_state": {
                    "2:uses:not-yet:current": 3,
                    "2:uses:not-yet:max": 3,
                },
                "_monster_modifier_state": {},
                "_monster_sequence_state": {},
                "_pending_prompts": {},
                "_name_role_memory": {"Gunner": "enemy"},
                "active_cid": 1,
                "round_num": 1,
                "turn_num": 1,
            }
        )
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants.get(cid), None, cid)
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._lan_force_state_broadcast = lambda: None
        self.app._log = lambda *args, **kwargs: None
        self.app._oplog = lambda *args, **kwargs: None
        self.app._lan_feet_per_square = lambda: 5.0
        self.app._combatant_distance_ft = lambda source, target: 5.0
        self.app._combatants_are_hostile = lambda source, target: False

        self.applied_damage = []

        def _apply_damage(attacker_cid, target_cid, attack_name, damage_entries):
            total = sum(int(entry.get("amount") or 0) for entry in damage_entries if isinstance(entry, dict))
            target = self.app.combatants[int(target_cid)]
            target.hp = max(0, int(getattr(target, "hp", 0) or 0) - total)
            result = {
                "ok": True,
                "attacker_cid": int(attacker_cid),
                "target_cid": int(target_cid),
                "attack_name": str(attack_name or ""),
                "total_damage": int(total),
                "target_removed": False,
            }
            self.applied_damage.append(result)
            return result

        self.app._apply_map_attack_manual_damage = _apply_damage

        self.prompts_store = {}

        def mock_create_reaction_offer(**kwargs):
            prompt_id = str(kwargs.get("prompt_id") or "prompt")
            reactor_cid = int(kwargs.get("reactor_cid") or -1)
            prompt = {
                "prompt_id": prompt_id,
                "reactor_cid": reactor_cid,
                "reactor_name": self.app.combatants[reactor_cid].name if reactor_cid in self.app.combatants else "Reactor",
                "target_cid": kwargs.get("target_cid"),
                "metadata": copy.deepcopy(kwargs.get("extra_payload") or {}),
                "resume": copy.deepcopy(kwargs.get("resume_dispatch")),
            }
            self.prompts_store[prompt_id] = prompt
            return dict(prompt)

        prompts = mock.Mock()
        prompts.create_reaction_offer.side_effect = mock_create_reaction_offer
        prompts.get_prompt.side_effect = lambda prompt_id: self.prompts_store.get(prompt_id)
        prompts.pop_prompt.side_effect = lambda prompt_id: self.prompts_store.pop(prompt_id, None)
        prompts.all_prompts.side_effect = lambda: dict(self.prompts_store)

        player_service = mock.Mock()
        player_service.prompts = prompts
        self.player_patch = mock.patch.object(self.app, "_ensure_player_commands", return_value=player_service)
        self.player_patch.start()

    def tearDown(self):
        self.player_patch.stop()

    def _resolve_save_ability(self, target_cid, *, outcome="fail", save_total=None):
        payload = {
            "capability_id": "automatic-sweep",
            "targets": [{"target_cid": int(target_cid), "outcome": outcome}],
            "damage_rolls": [{"type": "fire", "rolled": 18, "rolled_success": 0}],
            "apply_damage": True,
            "apply_effects": False,
        }
        if save_total is not None:
            payload["targets"][0]["save_total"] = int(save_total)
        return self.app._dm_monster_capability_resolve_targets(actor_cid=1, payload=payload)

    def test_not_yet_use_updates_failed_save_authoritatively(self):
        pending = self._resolve_save_ability(2, save_total=11)
        self.assertTrue(pending["ok"])
        self.assertEqual(pending["resolution"], "pending_prompt")
        prompt_id = pending["pending_prompt_id"]
        self.assertEqual(len(self.applied_damage), 0)

        with mock.patch("dnd_initative_tracker.random.randint", return_value=5):
            resolved = self.app._resolve_monster_prompt(prompt_id, "use")

        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual(self.app.combatants[2].reaction_remaining, 0)
        self.assertEqual(self.app._monster_resource_state["2:uses:not-yet:current"], 2)
        resumed = resolved["result"]
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["results"][0]["outcome"], "success")
        self.assertTrue(resumed["results"][0]["save_result"]["passed"])
        self.assertEqual(self.app.combatants[2].hp, 40)
        self.assertEqual(len(self.applied_damage), 0)

    def test_not_yet_skip_leaves_failed_save_unchanged(self):
        pending = self._resolve_save_ability(2, save_total=11)
        prompt_id = pending["pending_prompt_id"]

        resolved = self.app._resolve_monster_prompt(prompt_id, "skip")

        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual(self.app.combatants[2].reaction_remaining, 1)
        self.assertEqual(self.app._monster_resource_state["2:uses:not-yet:current"], 3)
        resumed = resolved["result"]
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["results"][0]["outcome"], "fail")
        self.assertFalse(resumed["results"][0]["save_result"]["passed"])
        self.assertEqual(self.app.combatants[2].hp, 22)
        self.assertEqual(len(self.applied_damage), 1)

    def test_countermand_use_updates_failed_ally_save_authoritatively(self):
        pending = self._resolve_save_ability(4)
        self.assertTrue(pending["ok"])
        self.assertEqual(pending["resolution"], "pending_prompt")
        prompt_id = pending["pending_prompt_id"]
        self.assertEqual(self.prompts_store[prompt_id]["metadata"]["capability_id"], "countermand")

        self.app.combatants[4].saving_throws = {"dex": 2}
        self.app.combatants[4].ability_mods = {"dex": 2}
        with mock.patch("dnd_initative_tracker.random.randint", return_value=18):
            resolved = self.app._resolve_monster_prompt(prompt_id, "use")

        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual(self.app.combatants[3].reaction_remaining, 0)
        resumed = resolved["result"]
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["results"][0]["outcome"], "success")
        self.assertTrue(resumed["results"][0]["save_result"]["passed"])
        self.assertEqual(self.app.combatants[4].hp, 30)
        self.assertEqual(len(self.applied_damage), 0)

    def test_countermand_skip_leaves_failed_ally_save_unchanged(self):
        pending = self._resolve_save_ability(4)
        prompt_id = pending["pending_prompt_id"]

        resolved = self.app._resolve_monster_prompt(prompt_id, "skip")

        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual(self.app.combatants[3].reaction_remaining, 1)
        resumed = resolved["result"]
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["results"][0]["outcome"], "fail")
        self.assertFalse(resumed["results"][0]["save_result"]["passed"])
        self.assertEqual(self.app.combatants[4].hp, 12)
        self.assertEqual(len(self.applied_damage), 1)

    def test_no_prompt_when_all_eligible_sources_lack_reaction_or_use(self):
        self.app.combatants[2].reaction_remaining = 0
        self.app.combatants[3].reaction_remaining = 0
        self.app._monster_resource_state["2:uses:not-yet:current"] = 0
        result = self._resolve_save_ability(2, save_total=11)

        self.assertTrue(result["ok"], result)
        self.assertNotEqual(result.get("resolution"), "pending_prompt")
        self.assertEqual(len(self.prompts_store), 0)
        self.assertEqual(self.app.combatants[2].hp, 22)


if __name__ == "__main__":
    unittest.main()

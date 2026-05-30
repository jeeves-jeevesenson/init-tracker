import unittest
from dnd_initative_tracker import InitiativeTracker

class MockCombatant:
    def __init__(self, name, cid):
        self.name = name
        self.cid = cid
        self.monster_slug = None
        self.ac = 10
        self.hp = 10
        self.max_hp = 10
        self.is_pc = False
        self.action_remaining = 1
        self.bonus_action_remaining = 1
        self.reaction_remaining = 1
        self.condition_stacks = []
        self.speed = 30
        self.initiative = 10
        self.exhaustion_level = 0
        self.ally = False
        self.role = "enemy"

class TestBlackAndTanControlledBurst(unittest.TestCase):
    def setUp(self):
        self.app = InitiativeTracker()
        self.app._reset_combat()

        # Add a Rifleman
        self.rifleman_cid = 1
        self.rifleman = MockCombatant(name="Rifleman", cid=self.rifleman_cid)
        self.rifleman.monster_slug = "black-and-tan-rifleman"
        self.app.combatants[self.rifleman_cid] = self.rifleman

        # Add a target
        self.target_cid = 2
        self.target = MockCombatant(name="Target", cid=self.target_cid)
        self.target.ac = 10
        self.target.hp = 50
        self.target.max_hp = 50
        self.app.combatants[self.target_cid] = self.target

        self.app.in_combat = True
        self.app.current_cid = self.rifleman_cid
        self.app.round_num = 1
        self.app.turn_num = 1

        # Force loading of capabilities
        svc = self.app._ensure_monster_capabilities()
        self.rifleman_caps = svc.match_capabilities_for_combatant(self.rifleman)

    def test_controlled_burst_activation(self):
        """Test that Controlled Burst can be activated and sets state."""
        # Ensure ammo state first
        cap_rifle = next(c for c in self.rifleman_caps["capabilities"] if c["id"] == "armalite-rifle")
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        payload = {"capability_id": "controlled-burst"}
        result = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)

        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "modifier_activated")

        # Check state
        mods = self.app._monster_modifier_state.get(self.rifleman_cid, [])
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0]["capability_id"], "controlled-burst")

    def test_controlled_burst_toggle_disarm(self):
        """Test that Controlled Burst can be disarmed (toggle)."""
        # Ensure ammo state first
        cap_rifle = next(c for c in self.rifleman_caps["capabilities"] if c["id"] == "armalite-rifle")
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        # Arm
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})
        self.assertEqual(len(self.app._monster_modifier_state.get(self.rifleman_cid, [])), 1)

        # Disarm (Toggle)
        result = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "modifier_deactivated")
        self.assertEqual(len(self.app._monster_modifier_state.get(self.rifleman_cid, [])), 0)

    def test_controlled_burst_limit_once_per_turn(self):
        """Test that Controlled Burst can only be used once per turn."""
        # Ensure ammo state first
        cap_rifle = next(c for c in self.rifleman_caps["capabilities"] if c["id"] == "armalite-rifle")
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        payload = {"capability_id": "controlled-burst"}

        # Arm it
        result1 = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
        self.assertTrue(result1["ok"])

        # Resolve an attack to consume it
        atk_payload = {
            "capability_id": "armalite-rifle",
            "target_ids": [self.target_cid],
            "apply_damage": True,
            "damage_rolls": [{"rolled": 10, "type": "force"}]
        }
        self.app._dm_monster_capability_resolve_targets(actor_cid=self.rifleman_cid, payload=atk_payload)

        # Should now be marked used
        self.assertTrue(self.app._monster_resource_state.get(f"{self.rifleman_cid}:mod_used:controlled-burst"))

        # Second use same turn should fail
        result2 = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
        self.assertFalse(result2["ok"])
        self.assertIn("already used", result2["error"])

    def test_controlled_burst_applies_to_rifle(self):
        """Test that Controlled Burst adds damage to Armalite Rifle."""
        # Ensure ammo state first
        cap_rifle = next(c for c in self.rifleman_caps["capabilities"] if c["id"] == "armalite-rifle")
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        # Activate CB
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})

        # Execute Rifle attack
        # We need to mock random to ensure a hit and not a crit
        import unittest.mock as mock
        with mock.patch('random.randint', return_value=10): # d20 roll = 10, hits AC 10
            payload = {"capability_id": "armalite-rifle", "target_cid": self.target_cid}
            result = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
            self.assertTrue(result["ok"])
            # Check damage rolls in the automatic resolution
            damage_rolls = result.get("damage_rolls", [])
            # Should have original 1d12+4 AND extra 1d12
            self.assertEqual(len(damage_rolls), 2)
            formulas = [r["formula"] for r in damage_rolls]
            self.assertIn("1d12+4", formulas)
            self.assertIn("1d12", formulas)

            # Check that it cleared
            mods = self.app._monster_modifier_state.get(self.rifleman_cid, [])
            self.assertEqual(len(mods), 0)

    def test_controlled_burst_does_not_apply_to_knife(self):
        """Test that Controlled Burst does not apply to non-firearm attacks."""
        # Ensure ammo state first
        cap_rifle = next(c for c in self.rifleman_caps["capabilities"] if c["id"] == "armalite-rifle")
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        # Activate CB
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})

        # Execute Knife attack
        import unittest.mock as mock
        with mock.patch('random.randint', return_value=10):
            payload = {"capability_id": "knife", "target_cid": self.target_cid}
            result = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
            self.assertTrue(result["ok"])
            damage_rolls = result.get("damage_rolls", [])
            # Should ONLY have original 1d4+4
            self.assertEqual(len(damage_rolls), 1)
            self.assertEqual(damage_rolls[0]["formula"], "1d4+4")

            # Check that it is STILL ACTIVE (because Knife is not eligible)
            mods = self.app._monster_modifier_state.get(self.rifleman_cid, [])
            self.assertEqual(len(mods), 1)

    def test_controlled_burst_jam_risk(self):
        """Test that Controlled Burst jams on a natural 1."""
        # Ensure ammo state first
        cap_rifle = next(c for c in self.rifleman_caps["capabilities"] if c["id"] == "armalite-rifle")
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        # Activate CB
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})

        # Execute Rifle attack with nat 1
        import unittest.mock as mock
        with mock.patch('random.randint', return_value=1): # nat 1
            payload = {"capability_id": "armalite-rifle", "target_cid": self.target_cid}
            result = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
            self.assertTrue(result["ok"])
            self.assertEqual(result["misses"], 1)

            # Check Jammed state
            self.assertTrue(self.app._monster_resource_state.get(f"{self.rifleman_cid}:jammed:armalite-rifle"))

            # Verify we can't fire again
            result2 = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
            self.assertFalse(result2["ok"])
            self.assertIn("jammed", result2["error"])

    def test_controlled_burst_cleared_on_next_turn(self):
        """Test that Controlled Burst is cleared when the turn ends."""
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})
        self.assertEqual(len(self.app._monster_modifier_state.get(self.rifleman_cid, [])), 1)

        self.app._next_turn()
        self.assertEqual(len(self.app._monster_modifier_state.get(self.rifleman_cid, [])), 0)

if __name__ == "__main__":
    unittest.main()

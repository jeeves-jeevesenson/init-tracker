import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod

def _make_combatant(cid: int, name: str, *, ally: bool = False, is_pc: bool = False):
    c = tracker_mod.base.Combatant(
        cid=cid,
        name=name,
        hp=20,
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
    c.reaction_remaining = 1
    return c

class ReactionPromptAllyFilterTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._log = lambda *args, **kwargs: None
        
        # Setup allies (PCs)
        self.reactor = _make_combatant(1, "Reactor", ally=True, is_pc=True)
        self.ally_caster = _make_combatant(2, "AllyCaster", ally=True, is_pc=True)
        
        # Setup hostile (Enemy NPC)
        self.hostile_caster = _make_combatant(3, "HostileCaster", ally=False, is_pc=False)
        
        self.app.combatants = {
            1: self.reactor,
            2: self.ally_caster,
            3: self.hostile_caster,
        }

        # Bind methods needed for testing
        self.app._can_offer_counterspell_reaction = tracker_mod.InitiativeTracker._can_offer_counterspell_reaction.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._can_offer_spell_stopper_reaction = tracker_mod.InitiativeTracker._can_offer_spell_stopper_reaction.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._combatants_are_hostile = tracker_mod.InitiativeTracker._combatants_are_hostile.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._ensure_player_commands = tracker_mod.InitiativeTracker._ensure_player_commands.__get__(self.app, tracker_mod.InitiativeTracker)

    def test_counterspell_ally_prevention(self):
        # Case 1: Reactor and caster are allies. Should return (False, "ally")
        can_offer, reason = self.app._can_offer_counterspell_reaction(self.reactor, 2)
        self.assertFalse(can_offer)
        self.assertEqual(reason, "ally")

    def test_counterspell_hostile_allowed(self):
        # Case 2: Reactor and caster are hostiles. Should pass the ally check.
        # We mock helper methods to see if it moves past the ally check.
        self.app._counterspell_prepared_slots = mock.Mock(return_value=(True, 3))
        self.app._lan_positions = {}
        
        can_offer, reason = self.app._can_offer_counterspell_reaction(self.reactor, 3)
        self.assertTrue(can_offer)
        self.assertEqual(reason, "slot_available")

    def test_spell_stopper_ally_prevention(self):
        # Case 1: Reactor and caster are allies. Should return (False, "ally")
        can_offer, reason = self.app._can_offer_spell_stopper_reaction(self.reactor, 2)
        self.assertFalse(can_offer)
        self.assertEqual(reason, "ally")

    def test_spell_stopper_hostile_allowed(self):
        # Case 2: Reactor and caster are hostiles. Should pass the ally check.
        # We mock pool/dagger helper checks to see if it moves past the ally check.
        self.app._pc_name_for = mock.Mock(return_value="Reactor")
        self.app._profile_for_player_name = mock.Mock(return_value={})
        self.app._normalize_player_resource_pools = mock.Mock(return_value=[])
        
        # Reactor doesn't have dagger, so it should fail with "no_spell_stopper" instead of "ally"
        can_offer, reason = self.app._can_offer_spell_stopper_reaction(self.reactor, 3)
        self.assertFalse(can_offer)
        self.assertEqual(reason, "no_spell_stopper")

    def test_hellish_rebuke_ally_prevention(self):
        # Case 1: Victim (reactor) and attacker are allies.
        # should return None immediately from maybe_offer_hellish_rebuke without offering.
        # Let's bind and run the service method
        service = self.app._ensure_player_commands()
        
        req_id = service.maybe_offer_hellish_rebuke(
            victim_cid=1,
            attacker_cid=2,
            damage_total=10,
        )
        self.assertIsNone(req_id)

    def test_hellish_rebuke_hostile_allowed(self):
        # Case 2: Victim and attacker are hostile.
        # It should pass the check and try to check resources.
        self.app._can_offer_hellish_rebuke_reaction = mock.Mock(return_value=(False, "no_resource"))
        service = self.app._ensure_player_commands()
        
        req_id = service.maybe_offer_hellish_rebuke(
            victim_cid=1,
            attacker_cid=3,
            damage_total=10,
        )
        self.assertIsNone(req_id)
        # Verify it actually reached can_offer checks
        self.app._can_offer_hellish_rebuke_reaction.assert_called_once_with(self.reactor)

if __name__ == "__main__":
    unittest.main()

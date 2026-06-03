import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestBlackAndTanGate4(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="black-and-tan-vda-scorcher", is_pc=False, name="Scorcher 1"),
                2: mock.Mock(cid=2, monster_slug="black-and-tan-rifleman", is_pc=False, name="Rifleman 2"),
                3: mock.Mock(cid=3, is_pc=True, name="Hero", hp=100),
            },
            "_monster_resource_state": {},
            "_monster_modifier_state": {},
            "_monster_sequence_state": {},
            "_scorched_earth_protocol_end_round": None,
            "round_num": 1,
            "turn_num": 1,
            "in_combat": True
        })
        
        # Mocking methods
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._lan_force_state_broadcast = lambda: None
        self.app._log = lambda *args, **kwargs: None
        self.app._oplog = lambda *args, **kwargs: None
        self.app._trigger_scorched_earth_protocol = tracker_mod.InitiativeTracker._trigger_scorched_earth_protocol.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._is_scorched_earth_active = tracker_mod.InitiativeTracker._is_scorched_earth_active.__get__(self.app, tracker_mod.InitiativeTracker)
        
        # Mock DM service
        dm_service = mock.Mock()
        self.app._dm_service = dm_service
        self.dm_service = dm_service

    def test_scorcher_loading(self):
        """Scorcher should load and summarize correctly with executable actions."""
        service = MonsterCapabilityService()
        summary = service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-vda-scorcher", "name": "Scorcher"})
        self.assertTrue(summary["matched"])
        self.assertEqual(summary["monster_name"], "Black and Tan VDA Scorcher")
        
        actions = summary["groups"]["actions"]
        burst = next(a for a in actions if a["id"] == "flamethrower-burst")
        self.assertTrue(burst["executable"])
        self.assertEqual(burst["mechanics"]["ammo_cost"], 2)
        
        bonus = summary["groups"]["bonus_actions"]
        swap = next(a for a in bonus if a["id"] == "swap-tank")
        self.assertTrue(swap["executable"])
        
        traits = summary["groups"]["traits"]
        implant = next(a for a in traits if a["id"] == "protocol-implant")
        self.assertFalse(implant.get("executable", False))

    def test_scorcher_area_detection(self):
        """Scorcher area actions should have correct target_mode and area metadata."""
        service = MonsterCapabilityService()
        summary = service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-vda-scorcher", "name": "Scorcher"})
        
        actions = summary["groups"]["actions"]
        
        # Flamethrower Burst: 15ft cone
        burst = next(a for a in actions if a["id"] == "flamethrower-burst")
        self.assertEqual(burst["target_mode"], "area_manual")
        self.assertEqual(burst["area"]["shape"], "cone")
        self.assertEqual(burst["area"]["size"], 15)
        self.assertTrue(burst["multi_target_capable"])
        
        # Sweeping Burn: 30ft line
        sweeping = next(a for a in actions if a["id"] == "sweeping-burn")
        self.assertEqual(sweeping["target_mode"], "area_manual")
        self.assertEqual(sweeping["area"]["shape"], "line")
        self.assertEqual(sweeping["area"]["size"], 30)
        
        # Ignite Ground: 10ft square
        ignite = next(a for a in actions if a["id"] == "ignite-ground")
        self.assertEqual(ignite["target_mode"], "area_manual")
        self.assertEqual(ignite["area"]["shape"], "square")
        self.assertEqual(ignite["area"]["size"], 10)

    def test_scorcher_swap_tank_reload(self):
        """Swap Tank should reload the fuel-consuming actions."""
        # Setup initial state
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants[1], None, 1)
        self.app._dm_spend_combatant_turn_resource = lambda actor, spend: (True, None)
        self.app._dm_normalize_turn_spend = lambda spend, **kwargs: spend
        
        # Drain some fuel
        self.app._monster_resource_state["1:ammo:flamethrower-burst:current"] = 5
        self.app._monster_resource_state["1:ammo:flamethrower-burst:max"] = 10
        self.app._monster_resource_state["1:ammo:fuel:reserve_mags"] = 2
        
        # Inject the real _dm_monster_capability_execute but with mocks for dependencies
        self.app._dm_monster_capability_execute = tracker_mod.InitiativeTracker._dm_monster_capability_execute.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._monster_capability_ensure_resource_state = lambda cid, cap: None
        
        result = self.app._dm_monster_capability_execute(
            actor_cid=1,
            payload={"capability_id": "swap-tank", "spend": "bonus"}
        )
        
        self.assertTrue(result.get("ok"), f"Execution failed: {result.get('error')}")
        self.assertEqual(self.app._monster_resource_state["1:ammo:flamethrower-burst:current"], 10)
        self.assertEqual(self.app._monster_resource_state["1:ammo:fuel:reserve_mags"], 1)

    def test_scorcher_aoe_execution_preview(self):
        """AoE actions should return assisted resolution with multiple targets."""
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants[1], None, 1)
        self.app._dm_normalize_turn_spend = lambda spend, **kwargs: spend
        
        # Mock targets in area
        self.app.combatants[2] = mock.Mock(cid=2, hp=20, hp_max=20, name="Target 2", role="pc")
        self.app.combatants[3] = mock.Mock(cid=3, hp=20, hp_max=20, name="Target 3", role="pc")
        
        self.app._dm_monster_capability_execute = tracker_mod.InitiativeTracker._dm_monster_capability_execute.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._monster_capability_ensure_resource_state = lambda cid, cap: None
        
        # Test Flamethrower Burst with target_ids
        result = self.app._dm_monster_capability_execute(
            actor_cid=1,
            payload={
                "capability_id": "flamethrower-burst",
                "spend": "none",
                "target_ids": [2, 3]
            }
        )
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted")
        self.assertIn(2, result["target_ids"])
        self.assertIn(3, result["target_ids"])
        self.assertEqual(result["save_dc"], 15)
        self.assertEqual(result["save_ability"], "dex")

    def test_scorcher_area_hazard_execution(self):
        """Area hazards should execute with geometry."""
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants[1], None, 1)
        self.app._dm_normalize_turn_spend = lambda spend, **kwargs: spend
        self.app._dm_spend_combatant_turn_resource = lambda actor, spend: (True, None)
        
        self.app._dm_monster_capability_execute = tracker_mod.InitiativeTracker._dm_monster_capability_execute.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._monster_capability_ensure_resource_state = lambda cid, cap: None
        
        # Test Ignite Ground execution
        result = self.app._dm_monster_capability_execute(
            actor_cid=1,
            payload={
                "capability_id": "ignite-ground",
                "spend": "action",
                "aoe_geometry": {"shape": "square", "size": 10, "cx": 5, "cy": 5}
            }
        )
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "automatic")
        self.assertIn("placed on map", result["status"])

    def test_scorched_earth_protocol_trigger(self):
        """Protocol should apply condition only to eligible combatants."""
        result = self.app._trigger_scorched_earth_protocol()
        self.assertTrue(result["ok"])
        self.assertTrue(self.app._is_scorched_earth_active())
        self.assertEqual(self.app._scorched_earth_protocol_end_round, 151)
        
        # Should apply to Scorcher (cid=1) but not Rifleman (cid=2) or Hero (cid=3)
        self.dm_service.set_condition.assert_called_once_with(
            cid=1, ctype="protocol_implant_active", action="add", remaining_turns=150
        )

class TestLanDmSnapshotCrash(unittest.TestCase):
    def setUp(self):
        self.app = mock.create_autospec(tracker_mod.InitiativeTracker, instance=True)
        # We need isinstance(self.app, tracker_mod.InitiativeTracker) to be true
        # mock.create_autospec does this.
        
        # Re-reading LanController.__init__
        # self._tracker = app
        # self.cfg = LanConfig()
        # self.url_settings = LanUrlSettings()
        # ...
        
        # Let's try to just mock the minimal path.
        with mock.patch("dnd_initative_tracker.LanConfig"), \
             mock.patch("dnd_initative_tracker.LanUrlSettings"), \
             mock.patch("dnd_initative_tracker._make_client_error_logger"), \
             mock.patch("dnd_initative_tracker._make_lan_logger"):
            self.lan = tracker_mod.LanController(self.app)

    def test_dm_console_snapshot_payload_crash(self):
        """Should NOT crash when building DM console snapshot payload with pending prompts."""
        # Mock the path: self._ensure_player_commands().prompts.all_prompts().values()
        mock_prompts = mock.Mock()
        mock_prompts.all_prompts.return_value = {"p1": {"id": "p1", "msg": "test"}}
        
        mock_player_commands = mock.Mock()
        mock_player_commands.prompts = mock_prompts
        
        self.lan._ensure_player_commands = mock.Mock(return_value=mock_player_commands)
        
        # Mock dm_service
        self.lan._dm_service = mock.Mock()
        self.lan._dm_service.combat_snapshot.return_value = {"combatants": []}
        
        # Mock tactical snapshot
        self.app._dm_tactical_snapshot = mock.Mock(return_value={"units": []})
        
        # Mock tactical_map_enabled
        with mock.patch("dnd_initative_tracker.tactical_map_enabled", return_value=True):
            # This is where it should crash before the fix
            try:
                snapshot = self.lan._dm_console_snapshot_payload()
                self.assertIn("pending_prompts", snapshot)
            except AttributeError as e:
                if "'LanController' object has no attribute '_json_safe'" in str(e):
                    self.fail("LanController crashed with AttributeError: _json_safe")
                raise

if __name__ == "__main__":
    unittest.main()

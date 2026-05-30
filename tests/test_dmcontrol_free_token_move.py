import os
import sys
import types
import unittest
from pathlib import Path

sys.path.append(os.getcwd())
os.environ["INIT_TRACKER_HEADLESS"] = "1"

import dnd_initative_tracker as tracker_mod


class _DmPlaceHarness:
    _dm_place_combatant_on_map = tracker_mod.InitiativeTracker._dm_place_combatant_on_map
    _broadcast_tactical_state_update = tracker_mod.InitiativeTracker._broadcast_tactical_state_update

    def __init__(self) -> None:
        self.combatants = {
            1: types.SimpleNamespace(
                cid=1,
                name="Aelar",
                is_pc=True,
                hp=20,
                max_hp=20,
                speed=0,
                movement_remaining=0,
                action_remaining=0,
                bonus_action_remaining=0,
                reaction_remaining=0,
                rider_cid=None,
                mounted_by_cid=None,
            ),
            2: types.SimpleNamespace(
                cid=2,
                name="Goblin",
                is_pc=False,
                hp=7,
                max_hp=7,
                speed=30,
                movement_remaining=30,
                action_remaining=1,
                bonus_action_remaining=1,
                reaction_remaining=1,
                rider_cid=None,
                mounted_by_cid=None,
            ),
        }
        self.positions = {1: (1, 1), 2: (4, 4)}
        self._lan_positions = dict(self.positions)
        self.validate_calls = []
        self.synced_aoes = []
        self.environment_triggers = []
        self.tethered = []
        self.log_messages = []
        self.rebuild_calls = 0
        self.broadcast_calls = 0
        self.broadcast_include_static = []

    def _lan_live_map_data(self):
        return (10, 10, {(9, 9)}, {}, dict(self.positions))

    def _validate_relocation_destination(self, **kwargs):
        self.validate_calls.append(dict(kwargs))
        return (True, "")

    def _lan_set_token_position(self, cid: int, col: int, row: int):
        self.positions[int(cid)] = (int(col), int(row))

    def _lan_sync_fixed_to_caster_aoes(self, cid: int):
        self.synced_aoes.append(int(cid))

    def _lan_handle_environment_triggers_for_moved_unit(self, cid: int, origin, destination):
        self.environment_triggers.append((int(cid), tuple(origin), tuple(destination)))

    def _enforce_johns_echo_tether(self, cid: int):
        self.tethered.append(int(cid))

    def _log(self, message: str, cid=None):
        self.log_messages.append({"message": str(message), "cid": cid})

    def _rebuild_table(self, scroll_to_current=True):
        self.rebuild_calls += 1

    def _lan_force_state_broadcast(self, include_static=True):
        self.broadcast_calls += 1
        self.broadcast_include_static.append(bool(include_static))


class TestDmControlFreeTokenMove(unittest.TestCase):
    def test_dmcontrol_html_includes_free_move_controls(self):
        html = Path("assets/web/dmcontrol/index.html").read_text(encoding="utf-8")
        self.assertIn('id="freeMoveBtn"', html)
        self.assertIn('Free Move Token', html)
        self.assertIn('function toggleFreeMoveMode()', html)
        self.assertIn('function cancelFreeMoveMode(announce = false)', html)
        self.assertIn('async function executeFreeMove(cid, col, row)', html)
        self.assertIn('/api/dm/map/combatants/${cid}/place?workspace=dmcontrol', html)

    def test_dm_place_helper_repositions_pc_without_spending_turn_economy(self):
        app = _DmPlaceHarness()
        pc = app.combatants[1]

        result = app._dm_place_combatant_on_map(1, 7, 8)

        self.assertTrue(result["ok"])
        self.assertEqual((7, 8), app.positions[1])
        self.assertEqual(
            [
                {
                    "destination_col": 7,
                    "destination_row": 8,
                    "target_cid": 1,
                    "requires_unoccupied": True,
                }
            ],
            app.validate_calls,
        )
        self.assertEqual(0, pc.movement_remaining)
        self.assertEqual(0, pc.action_remaining)
        self.assertEqual(0, pc.bonus_action_remaining)
        self.assertEqual(0, pc.reaction_remaining)
        self.assertEqual([1], app.synced_aoes)
        self.assertEqual([(1, (1, 1), (7, 8))], app.environment_triggers)
        self.assertEqual([1], app.tethered)
        self.assertEqual(1, app.rebuild_calls)
        self.assertEqual(1, app.broadcast_calls)
        self.assertEqual([False], app.broadcast_include_static)
        self.assertTrue(any("placed on map" in entry["message"] for entry in app.log_messages))


if __name__ == "__main__":
    unittest.main()

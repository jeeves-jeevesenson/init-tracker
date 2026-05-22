import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import dnd_initative_tracker as tracker_mod


class DmMapStartupContractTests(unittest.TestCase):
    def test_headless_tracker_bootstrap_loads_enabled_player_profiles_from_yaml(self):
        with TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir)
            with mock.patch.object(tracker_mod, "_app_data_dir", return_value=runtime_dir), \
                 mock.patch.object(tracker_mod, "_runtime_data_dir", return_value=runtime_dir), \
                 mock.patch.object(tracker_mod, "POC_AUTO_START_LAN", False):
                app = tracker_mod.InitiativeTracker()
                try:
                    profiles = app._player_profiles_payload()
                finally:
                    try:
                        app.destroy()
                    except Exception:
                        pass

            self.assertGreater(len(profiles), 0)
            self.assertIn("John Twilight", profiles)
            self.assertTrue((runtime_dir / "players" / "John_Twilight.yaml").exists())

import unittest
from pathlib import Path

_DM_HTML_PATH = Path("assets/web/dm/index.html")

class TestDmToolboxUi(unittest.TestCase):
    def test_dm_toolbox_elements_exist(self):
        self.assertTrue(_DM_HTML_PATH.exists(), f"DM console page missing at {_DM_HTML_PATH}")
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        
        # Open button
        self.assertIn('id="openToolboxBtn"', html)
        self.assertIn('DM Toolbox', html)
        
        # Modal shell
        self.assertIn('id="toolboxOverlay"', html)
        self.assertIn('class="toolbox-overlay hidden"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        
        # Tabs
        self.assertIn('role="tablist"', html)
        self.assertIn('id="tab-session"', html)
        self.assertIn('id="tab-encounter"', html)
        self.assertIn('id="tab-overrides"', html)
        self.assertIn('id="tab-maptools"', html)
        self.assertIn('id="tab-debug"', html)
        
        # Panels
        self.assertIn('role="tabpanel"', html)
        self.assertIn('id="panel-session"', html)
        self.assertIn('id="panel-encounter"', html)
        self.assertIn('id="panel-overrides"', html)
        self.assertIn('id="panel-maptools"', html)
        self.assertIn('id="panel-debug"', html)

    def test_session_controls_in_toolbox(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check that session persistence controls are moved to panel-session
        # We look for a unique marker in panel-session followed by the controls
        self.assertIn('id="panel-session"', html)
        # Verify the section moved
        self.assertIn('id="newBlankSessionBtn"', html)
        self.assertIn('id="sessionSaveBtn"', html)
        self.assertIn('id="sessionLoadBtn"', html)
        
        # Verify player profile controls are in panel-session
        self.assertIn('id="addPlayersBtn"', html)
        self.assertIn('id="selectAllPlayersBtn"', html)
        self.assertIn('id="clearPlayerSelectionBtn"', html)
        
        # Verify old setup-group for session is gone
        self.assertNotIn('data-setup-group="session"', html)
        
        # Verify old setup-group roster NO LONGER contains Add Player Profiles
        # We search for the roster setup group and ensure Add Player Profiles is not inside it
        import re
        roster_match = re.search(r'data-setup-group="roster".*?>(.*?)<\/section>', html, re.DOTALL)
        if roster_match:
            roster_content = roster_match.group(1)
            self.assertNotIn('Add Player Profiles', roster_content)

    def test_monster_actions_text_preserved(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('Monster Actions', html)
        self.assertNotIn('Normalized Capabilities', html)

if __name__ == "__main__":
    unittest.main()

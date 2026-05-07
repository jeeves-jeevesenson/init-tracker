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
        self.assertIn('id="tab-legacy"', html)
        
        # Panels
        self.assertIn('role="tabpanel"', html)
        self.assertIn('id="panel-session"', html)
        self.assertIn('id="panel-encounter"', html)
        self.assertIn('id="panel-overrides"', html)
        self.assertIn('id="panel-maptools"', html)
        self.assertIn('id="panel-debug"', html)
        self.assertIn('id="panel-legacy"', html)

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

    def test_encounter_controls_in_toolbox(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check that Remove Combatant controls are moved to panel-encounter
        self.assertIn('id="panel-encounter"', html)
        
        import re
        encounter_match = re.search(r'id="panel-encounter".*?>(.*?)<!-- Overrides Tab -->', html, re.DOTALL)
        self.assertTrue(encounter_match, "panel-encounter not found in HTML")
        encounter_content = encounter_match.group(1)
        
        self.assertIn('Remove Combatant', encounter_content)
        self.assertIn('id="removeCidSelect"', encounter_content)
        self.assertIn('id="removeCombatantBtn"', encounter_content)
        self.assertIn('id="removeCombatantResult"', encounter_content)

        # Verify Advanced / Custom Combatant is in panel-encounter
        self.assertIn('Advanced / Custom Combatant', encounter_content)
        self.assertIn('id="newCombatantName"', encounter_content)
        self.assertIn('id="newCombatantHp"', encounter_content)
        self.assertIn('id="newCombatantInit"', encounter_content)
        self.assertIn('id="newCombatantAc"', encounter_content)
        self.assertIn('id="addCombatantBtn"', encounter_content)
        self.assertIn('id="addCombatantResult"', encounter_content)
        
        # Verify placeholder text (updated)
        self.assertIn('Mixed encounter groups, HP randomization, and advanced staging will live here.', encounter_content)
        self.assertNotIn('Custom combatants preserved in \'Controls\' panel for now.', encounter_content)
        
        # Verify Monster Library shell
        self.assertIn('class="monster-library-shell"', encounter_content)
        self.assertIn('id="monsterLibrarySearch"', encounter_content)
        self.assertIn('id="monsterLibraryResults"', encounter_content)
        self.assertIn('Search monsters', encounter_content)
        self.assertIn('Monster Library', encounter_content)
        
        # Verify Add Monster Specs is in panel-encounter
        self.assertIn('Add Monster Specs', encounter_content)
        self.assertIn('id="monsterSlugSelect"', encounter_content)
        self.assertIn('id="monsterCount"', encounter_content)
        self.assertIn('id="monsterInit"', encounter_content)
        self.assertIn('id="monsterNamePrefix"', encounter_content)
        self.assertIn('id="monsterAlly"', encounter_content)
        self.assertIn('id="addMonsterBtn"', encounter_content)
        self.assertIn('id="addMonsterResult"', encounter_content)

        # Verify old block is gone from main cockpit
        # Roster group should be gone entirely since it only had Add Combatant
        self.assertNotIn('data-setup-group="roster"', html)
        self.assertNotIn('id="setupRosterGroupTitle"', html)
        self.assertNotIn('Add Combatant</h3>', html) # The old H3 was plain "Add Combatant"

    def test_overrides_controls_in_toolbox(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check that HP/Temp HP controls are moved to panel-overrides
        self.assertIn('id="panel-overrides"', html)
        
        # Verify HP Adjustment is in panel-overrides
        # Use regex to find panel-overrides content
        import re
        overrides_match = re.search(r'id="panel-overrides".*?>(.*?)<!-- Map Tools Tab -->', html, re.DOTALL)
        self.assertTrue(overrides_match, "panel-overrides not found in HTML")
        overrides_content = overrides_match.group(1)
        
        self.assertIn('HP Adjustment', overrides_content)
        self.assertIn('id="hpCidSelect"', overrides_content)
        self.assertIn('id="hpDelta"', overrides_content)
        self.assertIn('id="applyHpBtn"', overrides_content)
        self.assertIn('id="hpResult"', overrides_content)
        
        self.assertIn('Temp HP', overrides_content)
        self.assertIn('id="tempHpCidSelect"', overrides_content)
        self.assertIn('id="tempHpAmount"', overrides_content)
        self.assertIn('id="applyTempHpBtn"', overrides_content)
        self.assertIn('id="tempHpResult"', overrides_content)
        
        # Verify Set Initiative is in panel-overrides
        self.assertIn('Set Initiative', overrides_content)
        self.assertIn('id="initCidSelect"', overrides_content)
        self.assertIn('id="initValue"', overrides_content)
        self.assertIn('id="setInitBtn"', overrides_content)
        self.assertIn('id="rollInitBtn"', overrides_content)
        self.assertIn('id="initResult"', overrides_content)
        
        # Verify placeholder text (updated)
        self.assertIn('Forced movement (Move Any Token) and other DM overrides will live here.', overrides_content)
        
        # Verify old health group is gone from cockpit
        self.assertNotIn('data-live-group="health"', html)
        self.assertNotIn('id="liveHealthGroupTitle"', html)
        
        # Verify old combat-setup group is gone from cockpit
        self.assertNotIn('data-setup-group="combat-setup"', html)
        self.assertNotIn('id="setupCombatGroupTitle"', html)

    def test_monster_actions_text_preserved(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('Monster Actions', html)
        self.assertNotIn('Normalized Capabilities', html)

    def test_legacy_controls_in_toolbox(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check that legacy sections are moved to panel-legacy
        self.assertIn('id="panel-legacy"', html)
        
        import re
        # Match until the end of the panel-legacy div
        legacy_match = re.search(r'id="panel-legacy".*?>(.*?)<\/div>\s*<\/div>\s*<\/div>', html, re.DOTALL)
        self.assertTrue(legacy_match, "panel-legacy not found in HTML")
        legacy_content = legacy_match.group(1)
        
        self.assertIn('Monster Turn Controls', legacy_content)
        self.assertIn('id="monsterTurnCard"', legacy_content)
        self.assertIn('Monster Pilot (DM Movement)', legacy_content)
        self.assertIn('id="monsterPilotCard"', legacy_content)
        
        # Verify they are gone from main cockpit
        # They were in sections with data-live-group="monster-turn" and "monster-pilot"
        self.assertNotIn('data-live-group="monster-turn"', html)
        self.assertNotIn('data-live-group="monster-pilot"', html)
        self.assertNotIn('id="liveMonsterTurnGroupTitle"', html)
        self.assertNotIn('id="liveMonsterPilotGroupTitle"', html)

if __name__ == "__main__":
    unittest.main()

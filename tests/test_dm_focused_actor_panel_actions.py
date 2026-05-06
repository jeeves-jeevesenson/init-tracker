import unittest
from pathlib import Path

_DM_HTML_PATH = Path("assets/web/dm/index.html")

class TestDmFocusedActorPanelActions(unittest.TestCase):
    def test_monster_actions_container_exists(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="focusedMonsterActions"', html)
        self.assertIn('Monster Actions', html)

    def test_css_classes_exist(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('.focused-actor-actions-list', html)
        self.assertIn('.focused-action-group', html)
        self.assertIn('.focused-action-group-title', html)
        self.assertIn('.focused-action-card', html)
        self.assertIn('.focused-action-card.is-selected', html)
        self.assertIn('.focused-action-card.is-expanded', html)
        self.assertIn('.focused-action-details', html)
        self.assertIn('.focused-action-desc', html)
        self.assertIn('.focused-action-meta-grid', html)

    def test_js_logic_exists(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('let monsterCapabilitiesByCid = {};', html)
        self.assertIn('let focusedActorSelectedActionId = null;', html)
        self.assertIn('let focusedActorExpandedActionId = null;', html)
        self.assertIn('let focusedActorTargetModeEnabled = false;', html)
        self.assertIn('let focusedActorTargetActionId = null;', html)
        self.assertIn('let focusedActorSelectedTargetCids = [];', html)
        self.assertIn('function updateMonsterCapabilityUis', html)
        self.assertIn('function renderCompactMonsterActions', html)
        self.assertIn('function selectFocusedActorAction', html)
        self.assertIn('function toggleFocusedActorTargetPreview', html)
        self.assertIn('function toggleFocusedActorSelectedTarget', html)
        self.assertIn('function clearFocusedActorSelectedTargets', html)
        self.assertIn('fetchMonsterCapabilities(cid)', html)

    def test_selection_expansion_rendering(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('onclick="selectFocusedActorAction(', html)
        self.assertIn('class="focused-action-details"', html)
        self.assertIn('class="focused-action-desc"', html)
        self.assertIn('class="focused-action-meta-grid"', html)
        self.assertIn('Execution and resolution coming later.', html)
        self.assertIn('Target Preview', html)
        self.assertIn('Cancel Preview', html)

    def test_target_tray_rendering(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('<h4>Target Tray</h4>', html)
        self.assertIn('Click tokens on the map to select targets.', html)
        self.assertIn('clearFocusedActorSelectedTargets()', html)
        self.assertIn('class="target-tray-list"', html)
        self.assertIn('class="target-tray-item"', html)
        self.assertIn('Resolution coming later.', html)

    def test_target_preview_rendering_logic(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('function renderFocusedActorTargetPreviewOverlay', html)
        self.assertIn('renderFocusedActorTargetPreviewOverlay(ctx, geometry, tactical)', html)
        self.assertIn('Targeting Preview Active', html)
        self.assertIn('focusedActorTargetModeEnabled ?', html)
        self.assertIn('evt.key === \'Escape\' && focusedActorTargetModeEnabled', html)
        self.assertIn('focusedActorSelectedTargetCids.length > 0', html)
        self.assertIn('selected)</span>', html)

    def test_highlighting_logic(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Source highlighting
        self.assertIn('Highlight Source Actor', html)
        self.assertIn('SOURCE', html)
        # Target highlighting
        self.assertIn('Highlight Selected Targets', html)
        self.assertIn('TARGET', html)
        self.assertIn('focusedActorSelectedTargetCids.forEach', html)
        self.assertIn('getFocusedActorTargetAdvisory', html)
        self.assertIn('OUT OF RANGE', html)
        self.assertIn('AOE ADVISORY', html)

    def test_advisory_validation_rendering(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('getFocusedActorTargetAdvisory(tid, cap, sourceUnit, targetUnit, tactical)', html)
        self.assertIn('advisory.text', html)
        self.assertIn('Selection is not blocked; DM decides.', html)
        self.assertIn('Likely in range', html)
        self.assertIn('Likely out of range', html)
        self.assertIn('AoE validation advisory only', html)

    def test_tactical_click_targeting(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('if (unit && focusedActorTargetModeEnabled) {', html)
        self.assertIn('toggleFocusedActorSelectedTarget(unit.cid);', html)

    def test_pc_behavior(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('Player character actions are managed by the player.', html)

    def test_fetching_state(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('Fetching actions...', html)

    def test_compact_rendering_logic(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check for some key parts of the renderCompactMonsterActions function
        self.assertIn('groupOrder = [\'actions\', \'bonus_actions\'', html)
        self.assertIn('m.attack_bonus !== undefined', html)
        self.assertIn('m.save_dc !== undefined', html)
        self.assertIn('m.damage.map(d => `${d.formula} ${d.type}`).join(\' + \')', html)

if __name__ == "__main__":
    unittest.main()

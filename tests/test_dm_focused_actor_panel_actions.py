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
        self.assertIn('function updateMonsterCapabilityUis', html)
        self.assertIn('function renderCompactMonsterActions', html)
        self.assertIn('function selectFocusedActorAction', html)
        self.assertIn('fetchMonsterCapabilities(cid)', html)

    def test_selection_expansion_rendering(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('onclick="selectFocusedActorAction(', html)
        self.assertIn('class="focused-action-details"', html)
        self.assertIn('class="focused-action-desc"', html)
        self.assertIn('class="focused-action-meta-grid"', html)
        self.assertIn('Targeting coming later.', html)

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

import unittest
from pathlib import Path

_DM_HTML_PATH = Path("assets/web/dm/index.html")

class TestDmFocusedActorPanel(unittest.TestCase):
    def test_focused_actor_panel_exists(self):
        self.assertTrue(_DM_HTML_PATH.exists(), f"DM console page missing at {_DM_HTML_PATH}")
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        
        # Panel container
        self.assertIn('id="focusedActorPanel"', html)
        self.assertIn('Focused Actor', html)
        self.assertIn('id="focusedActorContent"', html)
        
        # Empty state text
        self.assertIn('No active combatant. Start combat or set turn to focus an actor.', html)
        
        # CSS classes
        self.assertIn('.focused-actor-panel', html)
        self.assertIn('.actor-prototype-card', html)
        self.assertIn('.actor-stats-grid', html)
        self.assertIn('.stat-box', html)

    def test_js_functions_exist(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('function findFocusedActorFromSnapshot', html)
        self.assertIn('function renderFocusedActorPanel', html)
        
        # applySnapshot should call renderFocusedActorPanel
        self.assertIn('renderFocusedActorPanel(snap)', html)

    def test_panel_fields_and_placeholders(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check for labels in the JS template
        self.assertIn('HP', html)
        self.assertIn('AC', html)
        self.assertIn('Speed', html)
        self.assertIn('Init', html)
        self.assertIn('Passive', html)
        
        # PC View Only badge
        self.assertIn('View Only', html)
        self.assertIn('actor-view-only-badge', html)

        # Inspection and Active Turn badges
        self.assertIn('Inspecting', html)
        self.assertIn('Active Turn', html)
        
        # Placeholders
        self.assertIn('<h4>Movement</h4>', html)
        self.assertIn('<h4>Monster Actions</h4>', html)
        self.assertIn('<h4>Resources</h4>', html)
        self.assertIn('<h4>Traits / Details</h4>', html)

    def test_tactical_click_integration(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # handleTacticalCanvasClick should update focusedActorInspectCid and re-render
        self.assertIn('focusedActorInspectCid = unit.cid', html)
        self.assertIn('renderFocusedActorPanel(currentSnapshot)', html)
        
        # clearDmTransientStateForBlankSnapshot should clear focusedActorInspectCid
        # Simple string check is enough if we trust the context
        self.assertIn('focusedActorInspectCid = null;', html)

if __name__ == "__main__":
    unittest.main()

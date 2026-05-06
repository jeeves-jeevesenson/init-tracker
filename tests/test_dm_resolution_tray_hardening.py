import unittest
from pathlib import Path

_DM_HTML_PATH = Path("assets/web/dm/index.html")

class TestDmResolutionTrayHardening(unittest.TestCase):
    def test_in_flight_state_variable(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('let focusedActorResolutionInFlight = false;', html)

    def test_safety_text_exists(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('Apply Results will update combat state.', html)

    def test_buttons_disabled_when_in_flight(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check Prepare Resolution button
        self.assertIn('onclick="executeFocusedActorAction()" ${focusedActorResolutionInFlight ? \'disabled\' : \'\'}', html)
        # Check Apply Results button
        self.assertIn('onclick="resolveFocusedActorAction(true, true)" ${focusedActorResolutionInFlight ? \'disabled\' : \'\'}', html)

    def test_in_flight_logic_in_functions(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # executeFocusedActorAction
        self.assertIn('if (!actor || !focusedActorTargetActionId || focusedActorResolutionInFlight) return;', html)
        self.assertIn('focusedActorResolutionInFlight = true;', html)
        self.assertIn('finally {', html)
        self.assertIn('focusedActorResolutionInFlight = false;', html)
        
        # resolveFocusedActorAction
        self.assertIn('if (!actor || !focusedActorTargetActionId || !focusedActorResolutionPacket || focusedActorResolutionInFlight) return;', html)
        self.assertIn('focusedActorResolutionInFlight = true;', html)
        # It should clear error before starting
        self.assertIn('focusedActorResolutionError = null;', html)

    def test_cleanup_on_action_change(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # selectFocusedActorAction
        self.assertIn('if (focusedActorResolutionPacket && focusedActorTargetActionId !== capId)', html)
        self.assertIn('focusedActorResolutionPacket = null;', html)
        
        # toggleFocusedActorTargetPreview
        # Should clear resolution state when cancelling or switching
        self.assertIn('focusedActorResolutionPacket = null;', html)
        self.assertIn('focusedActorResolutionError = null;', html)

    def test_placeholder_removed(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertNotIn('Execution and resolution coming later.', html)

if __name__ == "__main__":
    unittest.main()

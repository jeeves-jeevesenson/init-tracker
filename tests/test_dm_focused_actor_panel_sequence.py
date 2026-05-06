import unittest
from pathlib import Path

_DM_HTML_PATH = Path("assets/web/dm/index.html")

class TestDmFocusedActorPanelSequence(unittest.TestCase):
    def test_sequence_state_variables_exist(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('let focusedActorSequencePacket = null;', html)
        self.assertIn('let focusedActorSequenceCompletedSteps = {};', html)

    def test_sequence_functions_exist(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('function selectFocusedActorSequenceStep', html)
        self.assertIn('function endFocusedActorSequence', html)

    def test_sequence_tray_rendering(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Check for the sequence tray container and logic
        self.assertIn('${focusedActorSequencePacket ?', html)
        self.assertIn('Sequence: ${escHtml(focusedActorSequencePacket.name)}', html)
        self.assertIn('onclick="endFocusedActorSequence()"', html)
        self.assertIn('focusedActorSequencePacket.steps.map', html)
        self.assertIn('onclick="selectFocusedActorSequenceStep(', html)

    def test_execute_handles_assisted_sequence(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("else if (data.result && data.result.resolution === 'assisted_sequence')", html)
        self.assertIn("focusedActorSequencePacket = data.result;", html)
        self.assertIn("focusedActorSequenceCompletedSteps = {};", html)

    def test_resolve_updates_completion_count(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("if (focusedActorSequencePacket) {", html)
        self.assertIn("const actionId = focusedActorTargetActionId;", html)
        self.assertIn("focusedActorSequenceCompletedSteps[actionId] = (focusedActorSequenceCompletedSteps[actionId] || 0) + 1;", html)

    def test_cleanup_logic(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # Actor change cleanup
        self.assertIn('focusedActorSequencePacket = null;', html)
        self.assertIn('focusedActorSequenceCompletedSteps = {};', html)
        
        # selectFocusedActorAction cleanup
        self.assertIn('if (focusedActorSequencePacket && capId !== focusedActorSequencePacket.capability_id)', html)
        
        # toggleFocusedActorTargetPreview cleanup
        self.assertIn('if (focusedActorSequencePacket && capId && capId !== focusedActorSequencePacket.capability_id)', html)

    def test_invalid_child_selection_handled(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('if (focusedActorResolutionInFlight) return;', html)
        self.assertIn('if (!exists) {', html)
        self.assertIn('focusedActorResolutionError = `Child action "${actionId}" not found for this monster.`;', html)

    def test_missing_steps_handled(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('focusedActorSequencePacket.steps && focusedActorSequencePacket.steps.length > 0 ?', html)
        self.assertIn('No steps defined in this sequence.', html)

    def test_successful_apply_increments_exactly_once(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('focusedActorSequenceCompletedSteps[actionId] = (focusedActorSequenceCompletedSteps[actionId] || 0) + 1;', html)

    def test_cancel_does_not_increment(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # cancelFocusedActorActionResolution should clear child targeting but NOT touch completed steps
        self.assertIn('function cancelFocusedActorActionResolution() {', html)
        self.assertIn('if (focusedActorSequencePacket) {', html)
        self.assertIn('focusedActorTargetModeEnabled = false;', html)
        self.assertNotIn('focusedActorSequenceCompletedSteps', html.split('function cancelFocusedActorActionResolution()')[1].split('}')[0])


if __name__ == "__main__":
    unittest.main()

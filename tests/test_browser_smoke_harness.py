import unittest
import subprocess
import os
import json
import shutil
import sys
from pathlib import Path

# Ensure the scripts directory is in the path if needed, 
# but we are calling it via subprocess which is safer for CLI tests.

class TestBrowserSmokeHarness(unittest.TestCase):
    def setUp(self):
        self.test_root = Path("logs/test-browser-smoke")
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_help(self):
        """Verify --help works and shows usage."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: browser-smoke-harness.py", result.stdout)
        self.assertIn("--list-scenarios", result.stdout)
        self.assertIn("--scenario", result.stdout)

    def test_list_scenarios(self):
        """Verify --list-scenarios shows the pending Scorcher scenario."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--list-scenarios"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("scorcher-ignite-ground", result.stdout)
        self.assertIn("Pilot: Scorcher Ignite Ground", result.stdout)

    def test_unknown_scenario(self):
        """Verify unknown scenario IDs fail with a useful message."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--scenario", "non-existent"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error: Unknown scenario 'non-existent'", result.stderr)

    def test_pending_scorcher_scenario_artifacts(self):
        """Verify the pending Scorcher scenario fails but creates artifacts."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", 
             "--scenario", "scorcher-ignite-ground", 
             "--artifact-root", str(self.test_root)],
            capture_output=True, text=True
        )
        # It should fail because it's not implemented yet (Gate 3 requirement)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not implemented until Gate 4", result.stderr)
        
        # Verify artifact directory was created
        self.assertTrue(self.test_root.exists())
        runs = list(self.test_root.iterdir())
        self.assertEqual(len(runs), 1)
        
        run_dir = runs[0]
        summary_path = run_dir / "summary.json"
        self.assertTrue(summary_path.exists())
        
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
            self.assertEqual(summary["scenario"], "scorcher-ignite-ground")
            self.assertEqual(summary["status"], "not_implemented")
            self.assertIn("dm", summary["roles"])
            self.assertIn("artifacts", summary)
            self.assertIn("server_log", summary["artifacts"])
            # Metadata placeholder
            self.assertIn("browser_context_metadata", summary)
            self.assertIn("dm", summary["browser_context_metadata"])

if __name__ == "__main__":
    unittest.main()

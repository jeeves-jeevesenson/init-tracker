import unittest
from unittest.mock import patch

import update_checker


class UpdateCheckerSafetyTests(unittest.TestCase):
    def test_normalize_github_repo_slug_supported_forms(self):
        self.assertEqual(
            update_checker.normalize_github_repo_slug("https://github.com/jeeves-jeevesenson/init-tracker.git"),
            "jeeves-jeevesenson/init-tracker",
        )
        self.assertEqual(
            update_checker.normalize_github_repo_slug("git@github.com:jeeves-jeevesenson/init-tracker.git"),
            "jeeves-jeevesenson/init-tracker",
        )
        self.assertEqual(
            update_checker.normalize_github_repo_slug("ssh://git@github.com/jeeves-jeevesenson/init-tracker"),
            "jeeves-jeevesenson/init-tracker",
        )

    def test_normalize_github_repo_slug_rejects_non_github(self):
        self.assertIsNone(update_checker.normalize_github_repo_slug("https://example.com/owner/repo.git"))

    def test_is_supported_update_checkout_rejects_mismatched_origin(self):
        with patch("update_checker.os.path.exists", return_value=True), patch(
            "update_checker.get_local_git_remote_url",
            return_value="https://github.com/jeeves-jeevesenson/dnd-initiative-tracker.git",
        ):
            ok, reason = update_checker.is_supported_update_checkout()
        self.assertFalse(ok)
        self.assertIn("not", reason.lower())

    def test_get_update_command_requires_supported_checkout(self):
        with patch("update_checker.is_supported_update_checkout", return_value=(False, "bad remote")):
            self.assertIsNone(update_checker.get_update_command())

    @patch("update_checker.is_supported_update_checkout", return_value=(True, ""))
    def test_get_update_command_returns_none_after_legacy_updater_removal(self, *_mocks):
        with patch("update_checker.sys.platform", "linux"):
            command = update_checker.get_update_command()
        self.assertIsNone(command)

    @patch("update_checker.is_supported_update_checkout", return_value=(True, ""))
    def test_manual_update_instructions_use_live_checkout_installer(self, *_mocks):
        instructions = update_checker.get_manual_update_instructions()
        self.assertIn("bash scripts/quick-install.sh", instructions)
        self.assertNotIn("update-linux.sh", instructions)
        self.assertNotIn("update-windows.ps1", instructions)


if __name__ == "__main__":
    unittest.main()

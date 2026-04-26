import unittest
from pathlib import Path


class LanNotificationClickFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")
        cls.sw = Path("assets/web/lan/sw.js").read_text(encoding="utf-8")

    def test_route_deep_link_suppresses_same_shell_navigation(self):
        self.assertIn("function shouldSuppressDeepLinkNavigation(target)", self.html)
        self.assertIn("logPageDebug(\"navigation_suppressed\"", self.html)
        self.assertIn("return isLanShellPath(targetPath) && isLanShellPath(normalizedPath);", self.html)
        self.assertLess(
            self.html.index("function shouldSuppressDeepLinkNavigation(target)"),
            self.html.index("location.href = target.href;"),
        )

    def test_notification_click_prefers_focusing_existing_client(self):
        self.assertIn('client.postMessage({ type: "notification-focus", url });', self.sw)
        self.assertIn("await client.focus();", self.sw)


if __name__ == "__main__":
    unittest.main()

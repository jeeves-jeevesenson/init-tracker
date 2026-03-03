import unittest
from pathlib import Path


class LanNotificationClickFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")
        cls.sw = Path("assets/web/lan/sw.js").read_text(encoding="utf-8")

    def test_route_deep_link_skips_same_url_refresh(self):
        self.assertIn("if (target.href === location.href){", self.html)
        self.assertIn("location.href = target.href;", self.html)
        self.assertLess(
            self.html.index("if (target.href === location.href){"),
            self.html.index("location.href = target.href;"),
        )

    def test_notification_click_prefers_focusing_existing_client(self):
        self.assertIn('client.postMessage({ type: "deep-link", url });', self.sw)
        self.assertIn("await client.focus();", self.sw)


if __name__ == "__main__":
    unittest.main()

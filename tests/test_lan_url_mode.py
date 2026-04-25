import types
import os
import subprocess
from pathlib import Path
from shutil import which
import unittest

import dnd_initative_tracker as tracker_mod

REPO_ROOT = Path(__file__).resolve().parent.parent
LAN_INDEX = REPO_ROOT / "assets" / "web" / "lan" / "index.html"


class LanUrlModeTests(unittest.TestCase):
    def _build_lan(self):
        lan = object.__new__(tracker_mod.LanController)
        lan.cfg = types.SimpleNamespace(host="0.0.0.0", port=8787)
        lan.url_settings = tracker_mod.LanUrlSettings()
        lan._resolve_local_ip = lambda: "192.168.1.10"
        return lan

    def test_http_mode_prefers_http_and_injects_http_base_url(self):
        lan = self._build_lan()
        lan.url_settings.url_mode = "http"

        self.assertEqual(lan.preferred_url(), "http://192.168.1.10:8787/")
        self.assertEqual(lan.html_injected_base_url(), "http://192.168.1.10:8787/")

    def test_https_mode_prefers_configured_https(self):
        lan = self._build_lan()
        lan.url_settings.url_mode = "https"
        lan.url_settings.public_https_url = " https://dnd.3045.network "

        self.assertEqual(lan.preferred_url(), "https://dnd.3045.network/")
        self.assertEqual(lan.html_injected_base_url(), "https://dnd.3045.network/")

    def test_both_mode_uses_undefined_injected_base_url_and_publishes_both(self):
        lan = self._build_lan()
        lan.url_settings.url_mode = "both"
        lan.url_settings.public_https_url = "https://dnd.3045.network/"

        urls = lan.published_urls()

        self.assertEqual(urls.get("http"), "http://192.168.1.10:8787/")
        self.assertEqual(urls.get("https"), "https://dnd.3045.network/")
        self.assertIsNone(lan.html_injected_base_url())


@unittest.skipUnless(which("node"), "node not installed")
class LanWebsocketUrlAssetTests(unittest.TestCase):
    def _ws_url_from_asset(self, page_url, injected_base=None):
        html = LAN_INDEX.read_text(encoding="utf-8")
        start = html.index("  const wsUrl = (() => {")
        end_marker = "  })();"
        end = html.index(end_marker, start) + len(end_marker)
        ws_url_snippet = html[start:end]
        script = (
            "const window = {};\n"
            "if (Object.prototype.hasOwnProperty.call(process.env, 'LAN_BASE_URL')) {\n"
            "  window.LAN_BASE_URL = process.env.LAN_BASE_URL;\n"
            "}\n"
            "const location = new URL(process.env.PAGE_URL);\n"
            "const wsPath = '/ws';\n"
            f"{ws_url_snippet}\n"
            "process.stdout.write(wsUrl);\n"
        )
        env = os.environ.copy()
        env["PAGE_URL"] = page_url
        if injected_base is None:
            env.pop("LAN_BASE_URL", None)
        else:
            env["LAN_BASE_URL"] = injected_base
        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_direct_http_page_load_uses_same_origin_websocket(self):
        self.assertEqual(
            self._ws_url_from_asset("http://192.168.0.58:8787/"),
            "ws://192.168.0.58:8787/ws",
        )

    def test_injected_base_url_cannot_override_direct_http_same_origin_websocket(self):
        self.assertEqual(
            self._ws_url_from_asset(
                "http://192.168.0.58:8787/",
                injected_base="https://dnd.3045.network/",
            ),
            "ws://192.168.0.58:8787/ws",
        )

    def test_https_page_load_uses_current_public_origin_websocket(self):
        self.assertEqual(
            self._ws_url_from_asset(
                "https://dnd.3045.network/",
                injected_base="https://stale.3045.network/",
            ),
            "wss://dnd.3045.network/ws",
        )

    def test_non_browser_origin_can_still_use_injected_public_base_url(self):
        self.assertEqual(
            self._ws_url_from_asset(
                "file:///tmp/lan-index.html",
                injected_base="https://dnd.3045.network/",
            ),
            "wss://dnd.3045.network/ws",
        )


if __name__ == "__main__":
    unittest.main()

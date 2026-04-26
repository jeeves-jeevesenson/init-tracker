import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - optional dependency
    TestClient = None

import dnd_initative_tracker as tracker_mod


class LanWsDebugGitignoreTests(unittest.TestCase):
    def test_logs_placeholder_and_generated_patterns_are_configured(self):
        repo_root = Path(__file__).resolve().parent.parent
        self.assertTrue((repo_root / "logs" / ".gitkeep").exists())
        gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("logs/*.log", gitignore)
        self.assertIn("logs/*.jsonl", gitignore)
        self.assertIn("logs/*.txt", gitignore)
        self.assertIn("!logs/.gitkeep", gitignore)


@unittest.skipUnless(TestClient is not None, "fastapi testclient not installed")
class LanWsDebugLoggingTests(unittest.TestCase):
    def _build_tracker(self):
        tracker = object.__new__(tracker_mod.InitiativeTracker)
        tracker.after = lambda *_args, **_kwargs: None
        tracker._oplog = lambda *_args, **_kwargs: None
        tracker._lan_snapshot = lambda **_kwargs: {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "units": [{"cid": 1, "name": "Alice"}],
            "turn_order": [1],
            "active_cid": 1,
            "round_num": 1,
            "obstacles": [],
            "rough_terrain": [],
            "map_state": {},
        }
        tracker._lan_pcs = lambda: [{"cid": 1, "name": "Alice"}]
        tracker._lan_claimable = lambda: [{"cid": 1, "name": "Alice"}]
        tracker._pc_name_for = lambda cid: "Alice" if int(cid) == 1 else f"cid:{cid}"
        return tracker

    def _build_lan(self):
        lan = tracker_mod.LanController(self._build_tracker())
        lan._clients_lock = threading.RLock()
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        lan._cached_snapshot = {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "units": [{"cid": 1, "name": "Alice"}],
            "turn_order": [1],
            "active_cid": 1,
            "round_num": 1,
            "obstacles": [],
            "rough_terrain": [],
            "map_state": {},
        }
        lan._cached_pcs = [{"cid": 1, "name": "Alice"}]
        lan._terrain_payload = lambda: {}
        lan._static_data_payload = lambda: {}
        lan._pcs_payload = lambda: [{"cid": 1, "name": "Alice"}]
        lan._dynamic_snapshot_payload = lambda: {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "units": [{"cid": 1, "name": "Alice"}],
            "turn_order": [1],
            "active_cid": 1,
            "round_num": 1,
            "claims": lan._claims_payload(),
            "map_state": {},
        }
        return lan

    def test_debug_flag_off_does_not_enable_websocket_debug_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"INITTRACKER_LOG_DIR": tmpdir}
            with mock.patch.dict("os.environ", env, clear=False):
                with mock.patch.dict("os.environ", {"INITTRACKER_WS_DEBUG": ""}, clear=False):
                    lan = self._build_lan()
                    lan._ws_debug_log("test", ws_id=1)
            self.assertFalse((Path(tmpdir) / "websocket_debug.jsonl").exists())
            self.assertFalse(lan._ws_debug_enabled)

    def test_debug_flag_on_logs_websocket_lifecycle_and_restored_claim(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"INITTRACKER_WS_DEBUG": "1", "INITTRACKER_LOG_DIR": tmpdir}
            with mock.patch.dict("os.environ", env, clear=False):
                lan = self._build_lan()
                client = TestClient(lan._fastapi_app)
                with client.websocket_connect("/ws") as ws:
                    ws.receive_json()
                    ws.receive_json()
                    ws.receive_json()
                    ws.receive_json()
                    ws.send_json({"type": "claim", "cid": 1, "client_id": "debug-client"})
                    while True:
                        payload = ws.receive_json()
                        if payload.get("type") == "claim_ack":
                            break
                with client.websocket_connect("/ws") as ws2:
                    ws2.receive_json()
                    ws2.receive_json()
                    ws2.receive_json()
                    ws2.receive_json()
                    ws2.send_json({"type": "client_hello", "client_id": "debug-client"})
                    while True:
                        payload = ws2.receive_json()
                        if payload.get("type") == "claim_ack":
                            self.assertEqual(payload.get("reason"), "restored_claim")
                            break

            log_path = Path(tmpdir) / "websocket_debug.jsonl"
            self.assertTrue(log_path.exists())
            entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            events = [entry.get("event") for entry in entries]
            self.assertIn("connect", events)
            self.assertIn("disconnect", events)
            restored = [entry for entry in entries if entry.get("event") == "restored_claim"]
            self.assertTrue(restored)
            self.assertEqual(restored[-1].get("claimed_character"), "Alice")
            self.assertIn("phase", restored[-1])

    def test_index_injects_debug_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"INITTRACKER_WS_DEBUG": "1", "INITTRACKER_LOG_DIR": tmpdir}
            with mock.patch.dict("os.environ", env, clear=False):
                lan = self._build_lan()
                client = TestClient(lan._fastapi_app)
                response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("window.INITTRACKER_WS_DEBUG=true;", response.text)


if __name__ == "__main__":
    unittest.main()

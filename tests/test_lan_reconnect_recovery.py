import threading
import queue
import unittest
import importlib.util
from unittest import mock

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional dependency in lightweight envs
    TestClient = None

import dnd_initative_tracker as tracker_mod

MAX_RECV_ATTEMPTS = 12
RECV_TIMEOUT_SECONDS = 2.5


@unittest.skipUnless(importlib.util.find_spec("httpx") is not None, "httpx not installed")
@unittest.skipUnless(TestClient is not None, "fastapi testclient not installed")
class LanReconnectRecoveryTests(unittest.TestCase):
    def _build_tracker(self):
        tracker = object.__new__(tracker_mod.InitiativeTracker)
        tracker.after = lambda *_args, **_kwargs: None
        tracker._oplog = lambda *_args, **_kwargs: None
        tracker._lan_snapshot = lambda **_kwargs: {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "units": [{"cid": 1, "name": "Alice"}],
            "turn_order": [1],
            "active_cid": 1,
            "round_num": 2,
            "obstacles": [],
            "rough_terrain": [],
            "map_state": {},
        }
        tracker._lan_pcs = lambda: [{"cid": 1, "name": "Alice"}]
        tracker._lan_claimable = lambda: [{"cid": 1, "name": "Alice"}]
        tracker._pc_name_for = lambda cid: "Alice" if int(cid) == 1 else f"cid:{cid}"
        return tracker

    def _build_client_and_lan(self):
        tracker = self._build_tracker()
        lan = tracker_mod.LanController(tracker)
        lan._clients_lock = threading.RLock()
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        lan._cached_snapshot = {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "units": [{"cid": 1, "name": "Alice"}],
            "turn_order": [1],
            "active_cid": 1,
            "round_num": 2,
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
            "round_num": 2,
            "claims": lan._claims_payload(),
        }
        return TestClient(lan._fastapi_app), lan

    def _recv_until_type(self, ws, msg_type):
        for _ in range(MAX_RECV_ATTEMPTS):
            result_queue = queue.Queue(maxsize=1)

            def _recv_target():
                try:
                    result_queue.put(("ok", ws.receive_json()))
                except (RuntimeError, ValueError, OSError) as exc:  # pragma: no cover - websocket transport errors
                    result_queue.put(("err", exc))

            worker = threading.Thread(target=_recv_target, daemon=True)
            worker.start()
            worker.join(timeout=RECV_TIMEOUT_SECONDS)
            if worker.is_alive():
                self.fail(f"Timed out waiting for websocket message while expecting {msg_type!r}.")
            status, payload = result_queue.get_nowait()
            if status == "err":
                raise payload
            if payload.get("type") == msg_type:
                return payload
        self.fail(f"Did not receive {msg_type!r} within bounded receive window.")

    def test_reconnect_restores_claim_after_socket_drop(self):
        client, _lan = self._build_client_and_lan()
        with client.websocket_connect("/ws") as ws:
            self._recv_until_type(ws, "state")
            ws.send_json({"type": "claim", "cid": 1, "client_id": "client-A"})
            first_ack = self._recv_until_type(ws, "claim_ack")
            self.assertTrue(first_ack.get("ok"))
            self.assertEqual(first_ack.get("claimed_cid"), 1)

        with client.websocket_connect("/ws") as ws2:
            self._recv_until_type(ws2, "state")
            ws2.send_json({"type": "client_hello", "client_id": "client-A"})
            restored = self._recv_until_type(ws2, "claim_ack")
            self.assertEqual(restored.get("reason"), "restored_claim")
            self.assertEqual(restored.get("claimed_cid"), 1)
            self.assertEqual(restored.get("you", {}).get("claimed_cid"), 1)
            self.assertGreaterEqual(int(restored.get("claim_rev") or 0), 1)

    def test_reconnect_recovery_state_request_returns_authoritative_you_payload(self):
        client, _lan = self._build_client_and_lan()
        with client.websocket_connect("/ws") as ws:
            self._recv_until_type(ws, "state")
            ws.send_json({"type": "claim", "cid": 1, "client_id": "client-B"})
            ack = self._recv_until_type(ws, "claim_ack")
            claimed_rev = int(ack.get("claim_rev") or 0)
            self.assertGreaterEqual(claimed_rev, 1)

        with client.websocket_connect("/ws") as ws2:
            self._recv_until_type(ws2, "state")
            ws2.send_json({"type": "client_hello", "client_id": "client-B"})
            restored = self._recv_until_type(ws2, "claim_ack")
            restored_rev = int(restored.get("claim_rev") or 0)
            self.assertGreaterEqual(restored_rev, claimed_rev)

            ws2.send_json({"type": "state_request"})
            state_payload = self._recv_until_type(ws2, "state")
            self.assertEqual(state_payload.get("you", {}).get("claimed_cid"), 1)
            self.assertEqual(int(state_payload.get("you", {}).get("claim_rev") or 0), restored_rev)
            self.assertIn("grid", state_payload.get("state", {}))
            self.assertEqual(state_payload.get("state", {}).get("active_cid"), 1)

    def test_duplicate_client_hello_does_not_repeat_restored_claim_followup(self):
        client, lan = self._build_client_and_lan()
        with client.websocket_connect("/ws") as ws:
            self._recv_until_type(ws, "state")
            ws.send_json({"type": "claim", "cid": 1, "client_id": "client-C"})
            self._recv_until_type(ws, "claim_ack")

        restore_calls = []
        original_claim_ws_async = lan._claim_ws_async

        async def tracked_claim_ws_async(ws_id, cid, note="Claimed", allow_override=False):
            if str(note) == "Restored claim.":
                restore_calls.append((int(ws_id), int(cid)))
            return await original_claim_ws_async(ws_id, cid, note=note, allow_override=allow_override)

        lan._claim_ws_async = tracked_claim_ws_async

        with client.websocket_connect("/ws") as ws2:
            self._recv_until_type(ws2, "state")
            ws2.send_json({"type": "client_hello", "client_id": "client-C"})
            self._recv_until_type(ws2, "claim_ack")
            ws2.send_json({"type": "client_hello", "client_id": "client-C"})
            ws2.send_json({"type": "state_request"})
            state_payload = self._recv_until_type(ws2, "state")
            self.assertEqual(state_payload.get("you", {}).get("claimed_cid"), 1)

        self.assertEqual(len(restore_calls), 1)

    def test_claim_revision_does_not_regress_after_reconnect_and_unclaim(self):
        client, _lan = self._build_client_and_lan()
        with client.websocket_connect("/ws") as ws:
            self._recv_until_type(ws, "state")
            ws.send_json({"type": "claim", "cid": 1, "client_id": "client-D"})
            claim_ack = self._recv_until_type(ws, "claim_ack")
            rev_after_claim = int(claim_ack.get("claim_rev") or 0)
            ws.send_json({"type": "unclaim", "client_id": "client-D"})
            unclaim_ack = self._recv_until_type(ws, "unclaim_ack")
            rev_after_unclaim = int(unclaim_ack.get("claim_rev") or 0)
            self.assertGreater(rev_after_unclaim, rev_after_claim)

        with client.websocket_connect("/ws") as ws2:
            self._recv_until_type(ws2, "state")
            ws2.send_json({"type": "client_hello", "client_id": "client-D"})
            ws2.send_json({"type": "state_request"})
            state_payload = self._recv_until_type(ws2, "state")
            self.assertIsNone(state_payload.get("you", {}).get("claimed_cid"))
            self.assertEqual(
                int(state_payload.get("you", {}).get("claim_rev") or 0),
                rev_after_unclaim,
            )


if __name__ == "__main__":
    unittest.main()

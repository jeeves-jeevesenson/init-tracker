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
from player_command_contracts import build_prompt_record, build_prompt_snapshot

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

    def test_state_request_includes_pending_prompt_snapshot_for_claimed_actor(self):
        tracker = self._build_tracker()
        tracker._pending_prompts = {
            "prompt-1": build_prompt_record(
                prompt_id="prompt-1",
                prompt_kind="reaction",
                trigger="shield",
                reactor_cid=1,
                eligible_actor_cids=[1],
                source_cid=2,
                target_cid=1,
                allowed_choices=[{"kind": "shield_yes", "label": "Yes", "mode": "ask"}],
                ws_ids=[101],
                prompt_text="Enemy attacks you with Sword.",
                metadata={"prompt_attack": "Sword"},
            )
        }
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
        client = TestClient(lan._fastapi_app)

        with client.websocket_connect("/ws") as ws:
            self._recv_until_type(ws, "state")
            ws.send_json({"type": "claim", "cid": 1, "client_id": "client-E"})
            self._recv_until_type(ws, "claim_ack")
            ws.send_json({"type": "state_request"})
            state_payload = self._recv_until_type(ws, "state")
            pending_prompt = state_payload.get("you", {}).get("pending_prompt") or {}
            self.assertEqual(pending_prompt.get("prompt_id"), "prompt-1")
            self.assertEqual(pending_prompt.get("trigger"), "shield")
            self.assertEqual((pending_prompt.get("contract") or {}).get("schema"), "player_command.prompt_snapshot")

    def test_state_request_contract_projection_locks_claim_turn_map_and_prompt_shape(self):
        tracker = self._build_tracker()
        prompt = build_prompt_record(
            prompt_id="prompt-1",
            prompt_kind="reaction",
            trigger="shield",
            reactor_cid=1,
            eligible_actor_cids=[1],
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes", "mode": "ask"}],
            ws_ids=[101],
            prompt_text="Enemy attacks you with Sword.",
            metadata={"prompt_attack": "Sword"},
            resolution={"player_visible": {"command": "attack_request", "label": "Resume attack"}},
            created_at=100.0,
            expires_at=112.0,
        )
        tracker._pending_prompts = {"prompt-1": prompt}
        client, _lan = self._build_client_and_lan()

        with client.websocket_connect("/ws") as ws:
            self._recv_until_type(ws, "state")
            ws.send_json({"type": "claim", "cid": 1, "client_id": "client-F"})
            claim_ack = self._recv_until_type(ws, "claim_ack")
            claim_rev = int(claim_ack.get("claim_rev") or 0)
            ws.send_json({"type": "state_request"})
            state_payload = self._recv_until_type(ws, "state")

        expected_prompt = build_prompt_snapshot(prompt)
        self.assertEqual(
            {
                "type": state_payload.get("type"),
                "state": {
                    "grid": state_payload.get("state", {}).get("grid"),
                    "active_cid": state_payload.get("state", {}).get("active_cid"),
                    "round_num": state_payload.get("state", {}).get("round_num"),
                    "claims": state_payload.get("state", {}).get("claims"),
                    "map_state": state_payload.get("state", {}).get("map_state"),
                },
                "you": {
                    "claimed_cid": state_payload.get("you", {}).get("claimed_cid"),
                    "claimed_name": state_payload.get("you", {}).get("claimed_name"),
                    "claim_rev": state_payload.get("you", {}).get("claim_rev"),
                    "pending_prompts": state_payload.get("you", {}).get("pending_prompts"),
                    "pending_prompt": state_payload.get("you", {}).get("pending_prompt"),
                },
            },
            {
                "type": "state",
                "state": {
                    "grid": {"cols": 12, "rows": 8, "ready": True},
                    "active_cid": 1,
                    "round_num": 2,
                    "claims": {"1": "client-F"},
                    "map_state": {},
                },
                "you": {
                    "claimed_cid": 1,
                    "claimed_name": "Alice",
                    "claim_rev": claim_rev,
                    "pending_prompts": [expected_prompt],
                    "pending_prompt": expected_prompt,
                },
            },
        )


class LanReconnectPayloadContractUnitTests(unittest.TestCase):
    def test_payload_builders_lock_claim_turn_map_and_prompt_shape_without_http_stack(self):
        tracker = object.__new__(tracker_mod.InitiativeTracker)
        tracker._pending_prompts = {}
        tracker._pc_name_for = lambda cid: "Alice" if int(cid) == 1 else f"cid:{cid}"
        prompt = build_prompt_record(
            prompt_id="prompt-1",
            prompt_kind="reaction",
            trigger="shield",
            reactor_cid=1,
            eligible_actor_cids=[1],
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes", "mode": "ask"}],
            ws_ids=[101],
            prompt_text="Enemy attacks you with Sword.",
            metadata={"prompt_attack": "Sword"},
            resolution={"player_visible": {"command": "attack_request", "label": "Resume attack"}},
            created_at=100.0,
            expires_at=112.0,
        )
        tracker._ensure_player_commands().prompts.replace_prompts({"prompt-1": prompt})

        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = tracker
        lan._clients_lock = threading.RLock()
        lan._claims = {101: 1}
        lan._client_ids = {101: "client-F"}
        lan._client_id_claims = {"client-F": 1}
        lan._client_claim_revs = {"client-F": 3}
        lan._ws_claim_revs = {}
        lan._cached_pcs = [{"cid": 1, "name": "Alice"}]
        lan._cached_snapshot = {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "obstacles": [],
            "rough_terrain": [],
            "map_state": {},
        }
        lan._dynamic_snapshot_payload = lambda: {
            "grid": {"cols": 12, "rows": 8, "ready": True},
            "active_cid": 1,
            "round_num": 2,
            "claims": {"1": "client-F"},
        }
        lan._ensure_player_commands = tracker._ensure_player_commands

        expected_prompt = build_prompt_snapshot(prompt)
        self.assertEqual(
            {
                "state": lan._view_only_state_payload(lan._dynamic_snapshot_payload()),
                "you": lan._build_you_payload(101),
            },
            {
                "state": {
                    "grid": {"cols": 12, "rows": 8, "ready": True},
                    "active_cid": 1,
                    "round_num": 2,
                    "claims": {"1": "client-F"},
                    "rough_terrain": [],
                    "obstacles": [],
                    "map_state": {},
                },
                "you": {
                    "claimed_cid": 1,
                    "claimed_name": "Alice",
                    "claim_rev": 3,
                    "pending_prompts": [expected_prompt],
                    "pending_prompt": expected_prompt,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()

import asyncio
import threading
import unittest
from types import SimpleNamespace

import dnd_initative_tracker as tracker_mod


class _TrackerStub:
    def __init__(self):
        self.combatants = {
            1: SimpleNamespace(cid=1, name="Aelar", is_pc=True),
        }

    def _pc_name_for(self, cid: int) -> str:
        if int(cid) == 1:
            return "Aelar"
        return f"cid:{cid}"

    def _oplog(self, *_args, **_kwargs):
        return None


class LanClientHelloReconnectTests(unittest.TestCase):
    def _build_lan(self):
        ws_id = 11
        sent_payloads = []

        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _TrackerStub()
        lan._clients_lock = threading.RLock()
        lan._clients = {ws_id: object()}
        lan._claims = {}
        lan._cid_to_ws = {}
        lan._cid_to_host = {}
        lan._client_hosts = {ws_id: "10.0.0.5"}
        lan._client_ids = {}
        lan._client_id_to_ws = {}
        lan._client_id_claims = {}
        lan._client_claim_revs = {}
        lan._ws_claim_revs = {}
        lan._cached_pcs = [{"cid": 1, "name": "Aelar", "is_pc": True}]
        lan._spell_debug_log = lambda *_args, **_kwargs: None

        async def _send_async(target_ws_id, payload):
            sent_payloads.append((int(target_ws_id), dict(payload)))

        lan._send_async = _send_async
        return lan, ws_id, sent_payloads

    @staticmethod
    def _payloads_of_type(sent_payloads, typ: str):
        return [payload for _ws_id, payload in sent_payloads if payload.get("type") == typ]

    def test_client_hello_without_saved_claim_still_returns_authoritative_claim_ack(self):
        lan, ws_id, sent_payloads = self._build_lan()
        lan._client_claim_revs["client-1"] = 2

        asyncio.run(lan._handle_client_hello_async(ws_id, "10.0.0.5", {"type": "client_hello", "client_id": "client-1"}))

        self.assertEqual(lan._client_ids.get(ws_id), "client-1")
        claim_acks = self._payloads_of_type(sent_payloads, "claim_ack")
        self.assertEqual(len(claim_acks), 1)
        ack = claim_acks[0]
        self.assertTrue(ack.get("ok"))
        self.assertEqual(ack.get("reason"), "no_saved_claim")
        self.assertIsNone(ack.get("claimed_cid"))
        self.assertEqual(ack.get("claim_rev"), 2)
        self.assertEqual((ack.get("you") or {}).get("claimed_cid"), None)

    def test_client_hello_restores_cached_claim_and_claim_revision(self):
        lan, ws_id, sent_payloads = self._build_lan()
        lan._client_id_claims["client-1"] = 1
        lan._client_claim_revs["client-1"] = 5

        asyncio.run(lan._handle_client_hello_async(ws_id, "10.0.0.5", {"type": "client_hello", "client_id": "client-1"}))

        self.assertEqual(lan._claims.get(ws_id), 1)
        force_claims = self._payloads_of_type(sent_payloads, "force_claim")
        self.assertEqual(len(force_claims), 1)
        self.assertEqual(force_claims[0].get("cid"), 1)
        self.assertEqual(force_claims[0].get("text"), "Restored claim.")

        claim_acks = self._payloads_of_type(sent_payloads, "claim_ack")
        self.assertEqual(len(claim_acks), 1)
        ack = claim_acks[0]
        self.assertTrue(ack.get("ok"))
        self.assertEqual(ack.get("reason"), "restored_claim")
        self.assertEqual(ack.get("claimed_cid"), 1)
        self.assertEqual(ack.get("claim_rev"), 5)
        self.assertEqual((ack.get("you") or {}).get("claimed_cid"), 1)
        self.assertEqual((ack.get("you") or {}).get("claim_rev"), 5)

    def test_client_hello_with_existing_ws_claim_returns_authoritative_ack(self):
        lan, ws_id, sent_payloads = self._build_lan()
        lan._claims[ws_id] = 1
        lan._cid_to_ws[1] = {ws_id}
        lan._client_id_claims["client-1"] = 1
        lan._client_claim_revs["client-1"] = 7

        asyncio.run(lan._handle_client_hello_async(ws_id, "10.0.0.5", {"type": "client_hello", "client_id": "client-1"}))

        force_claims = self._payloads_of_type(sent_payloads, "force_claim")
        self.assertEqual(force_claims, [])

        claim_acks = self._payloads_of_type(sent_payloads, "claim_ack")
        self.assertEqual(len(claim_acks), 1)
        ack = claim_acks[0]
        self.assertTrue(ack.get("ok"))
        self.assertEqual(ack.get("reason"), "already_synced")
        self.assertEqual(ack.get("claimed_cid"), 1)
        self.assertEqual(ack.get("claim_rev"), 7)
        self.assertEqual((ack.get("you") or {}).get("claimed_cid"), 1)


class LanReconnectUiContractTests(unittest.TestCase):
    def test_lan_client_marks_claim_state_as_resyncing_until_authoritative_update(self):
        with open("/home/runner/work/init-tracker/init-tracker/assets/web/lan/index.html", "r", encoding="utf-8") as handle:
            text = handle.read()

        self.assertIn("let claimResyncPending = false;", text)
        self.assertIn("beginReconnectClaimResync();", text)
        self.assertIn("const shouldDeferNullClaimSync = claimResyncPending", text)
        self.assertIn('claimStatus === "resyncing" ? "(resyncing…)" : "(unclaimed)"', text)


if __name__ == "__main__":
    unittest.main()

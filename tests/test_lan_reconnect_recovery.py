import unittest
from pathlib import Path


class LanReconnectRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")

    def test_reconnect_uses_recovery_gate_before_connected(self):
        self.assertIn("function reconnectRecoveryReady(){", self.html)
        self.assertIn("beginReconnectRecoveryCycle();", self.html)
        self.assertIn("setConn(false, \"Recovering…\");", self.html)
        self.assertIn("setConn(true, \"Connected\");", self.html)

    def test_reconnect_fallback_requests_authoritative_ws_state_once(self):
        self.assertIn("if (reconnectFallbackRequested) return;", self.html)
        self.assertIn("send({type:\"state_request\"});", self.html)
        self.assertIn("send({type:\"grid_request\"});", self.html)
        self.assertIn("send({type:\"terrain_request\"});", self.html)

    def test_reconnect_claim_sync_toast_is_suppressed(self):
        self.assertIn("function isReconnectClaimSyncToast(text){", self.html)
        self.assertIn("if (!(reconnectRecoveryPending && isReconnectClaimSyncToast(msg.text))){", self.html)

    def test_stale_claim_revision_guard_remains_monotonic(self):
        self.assertIn("if (Number.isFinite(revValue) && revValue < claimRev){", self.html)


if __name__ == "__main__":
    unittest.main()

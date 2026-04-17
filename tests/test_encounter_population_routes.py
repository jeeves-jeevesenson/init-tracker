import threading
import types
import unittest
from unittest import mock

try:
    import httpx  # noqa: F401
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

import dnd_initative_tracker as tracker_mod


class _AppStub:
    combatants = {}

    def __init__(self):
        self._route_calls = []

    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_snapshot(self):
        return {"grid": None, "obstacles": [], "units": [], "active_cid": None, "round_num": 0}

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None

    def _add_player_profile_combatants_via_service(self, names, *, skip_existing=False):
        self._route_calls.append({"names": list(names), "skip_existing": bool(skip_existing)})
        return {"ok": True, "added": ["Aelar"], "skipped": []}

    def _create_pc_from_profile(self, *_args, **_kwargs):
        raise AssertionError("route should delegate through _add_player_profile_combatants_via_service")


@unittest.skipUnless(TestClient is not None, "fastapi testclient/httpx not installed")
class EncounterPopulationRouteTests(unittest.TestCase):
    def _build_client_with_app(self):
        app = _AppStub()
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = app
        lan.cfg = types.SimpleNamespace(
            host="127.0.0.1",
            port=0,
            vapid_public_key=None,
            allowlist=[],
            denylist=[],
            admin_password=None,
        )
        lan._server_thread = None
        lan._fastapi_app = None
        lan._polling = False
        lan._cached_snapshot = {}
        lan._cached_pcs = []
        lan._clients_lock = threading.RLock()
        lan._actions = None
        lan._best_lan_url = lambda: "http://127.0.0.1:0"
        lan._tick = lambda: None
        lan._append_lan_log = lambda *_args, **_kwargs: None
        lan._init_admin_auth = lambda: None
        lan._admin_password_hash = b"configured"
        lan._admin_password_salt = b"salt"
        lan._admin_tokens = {}
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda *_args, **_kwargs: False
        lan._issue_admin_token = lambda: "token"
        lan._is_admin_token_valid = lambda token: token == "token"

        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app), app

    def test_encounter_players_add_route_uses_canonical_wrapper(self):
        client, app = self._build_client_with_app()

        response = client.post(
            "/api/encounter/players/add",
            json={"names": ["Aelar"]},
            headers={"Authorization": "Bearer token"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "added": ["Aelar"], "skipped": []}, response.json())
        self.assertEqual(
            [{"names": ["Aelar"], "skip_existing": True}],
            app._route_calls,
        )


if __name__ == "__main__":
    unittest.main()

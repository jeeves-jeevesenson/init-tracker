import threading
import types
import unittest
from unittest import mock
from pathlib import Path

try:
    import httpx
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

import dnd_initative_tracker as tracker_mod

class _CombatantStub:
    def __init__(self, name):
        self.name = name

class _AppStub:
    def __init__(self):
        self.combatants = {}
        self._monster_specs = []

    def _oplog(self, *args, **kwargs): return None
    def _lan_snapshot(self): return {"units": []}
    def _lan_pcs(self): return []
    def after(self, *args, **kwargs): return None
    
    def _find_monster_spec_by_slug(self, slug):
        spec = mock.Mock()
        spec.name = "Black and Tan Rifleman"
        return spec

    def _add_monster_spec_combatants_via_service(self, entries):
        added = []
        for entry in entries:
            name = entry["name"]
            cid = len(self.combatants) + 1
            c = _CombatantStub(name)
            self.combatants[cid] = c
            added.append(name)
        return {"ok": True, "added": added}

@unittest.skipUnless(TestClient is not None, "fastapi testclient/httpx not installed")
class TestDmMonsterAddNumbering(unittest.TestCase):
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
        lan._clients_lock = threading.RLock()
        lan._init_admin_auth = lambda: None
        lan._admin_password_hash = b"hash"
        lan._admin_password_salt = b"salt"
        lan._admin_tokens = {}
        lan._issue_admin_token = lambda: "token"
        lan._is_admin_token_valid = lambda token: token == "token"
        lan._tick = lambda: None
        lan._append_lan_log = lambda *args, **kwargs: None
        lan._best_lan_url = lambda: "http://127.0.0.1:0"
        lan._polling = False
        lan._ws_server = None

        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app), app

    def test_repeated_single_spawn_numbering(self):
        client, app = self._build_client_with_app()
        headers = {"Authorization": "Bearer token"}
        
        # Add 1
        resp = client.post("/api/dm/encounter/monsters/add", 
                           json={"monster_slug": "black-and-tan-rifleman", "count": 1},
                           headers=headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(["Black and Tan Rifleman 1"], resp.json()["added"])
        
        # Add another 1
        resp = client.post("/api/dm/encounter/monsters/add", 
                           json={"monster_slug": "black-and-tan-rifleman", "count": 1},
                           headers=headers)
        self.assertEqual(["Black and Tan Rifleman 2"], resp.json()["added"])
        
        # Add a third 1
        resp = client.post("/api/dm/encounter/monsters/add", 
                           json={"monster_slug": "black-and-tan-rifleman", "count": 1},
                           headers=headers)
        self.assertEqual(["Black and Tan Rifleman 3"], resp.json()["added"])

    def test_multi_spawn_numbering(self):
        client, app = self._build_client_with_app()
        headers = {"Authorization": "Bearer token"}
        
        # Add 3 at once
        resp = client.post("/api/dm/encounter/monsters/add", 
                           json={"monster_slug": "goblin", "count": 3},
                           headers=headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(["Black and Tan Rifleman 1", "Black and Tan Rifleman 2", "Black and Tan Rifleman 3"], 
                         resp.json()["added"])

    def test_existing_unsuffixed_occupies_slot_1(self):
        client, app = self._build_client_with_app()
        headers = {"Authorization": "Bearer token"}
        
        # Manually add an unsuffixed one
        app.combatants[100] = _CombatantStub("Black and Tan Rifleman")
        
        # Add 1 via route
        resp = client.post("/api/dm/encounter/monsters/add", 
                           json={"monster_slug": "black-and-tan-rifleman", "count": 1},
                           headers=headers)
        self.assertEqual(["Black and Tan Rifleman 2"], resp.json()["added"])

if __name__ == "__main__":
    unittest.main()

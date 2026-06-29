import unittest

from fastapi.testclient import TestClient

from server_app import create_app
from server_runtime import ServerRuntimeFacade


class ServerAppTests(unittest.TestCase):
    def test_app_factory_owns_runtime_facade(self):
        app = create_app()

        self.assertFalse(app.state.ready)
        self.assertIsNone(app.state.lan_controller)
        self.assertIsInstance(app.state.runtime, ServerRuntimeFacade)
        self.assertFalse(app.state.runtime.is_ready())

    def test_lifespan_updates_app_and_runtime_readiness(self):
        app = create_app()

        with TestClient(app) as client:
            self.assertTrue(app.state.ready)
            self.assertTrue(app.state.runtime.is_ready())

            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json(), {"status": "healthy", "ready": True})

            api_health = client.get("/api/health")
            self.assertEqual(api_health.status_code, 200)
            self.assertEqual(api_health.json(), {"status": "healthy", "ready": True})

            ready = client.get("/ready")
            self.assertEqual(ready.status_code, 200)
            self.assertEqual(ready.json(), {"status": "ready"})

            api_ready = client.get("/api/ready")
            self.assertEqual(api_ready.status_code, 200)
            self.assertEqual(api_ready.json(), {"status": "ready"})

        self.assertFalse(app.state.ready)
        self.assertFalse(app.state.runtime.is_ready())

    def test_unready_endpoints_and_facade_before_lifespan(self):
        app = create_app()
        client = TestClient(app)

        self.assertFalse(app.state.ready)
        self.assertFalse(app.state.runtime.is_ready())

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "healthy", "ready": False})

        ready = client.get("/ready")
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(ready.json(), {"status": "not ready"})

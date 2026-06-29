import unittest

from fastapi.testclient import TestClient

from server_app import create_app
from server_runtime import (
    ServerRuntimeFacade,
    RuntimeCommand,
    RuntimeCommandResult,
    RuntimeSnapshotRequest,
    RuntimeSnapshotResult,
)


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

    def test_command_contract_constructible(self):
        command = RuntimeCommand(command_type="test_action", payload={"key": "val"})
        self.assertEqual(command.command_type, "test_action")
        self.assertEqual(command.payload, {"key": "val"})

    def test_command_result_constructible(self):
        result = RuntimeCommandResult(success=True, message="done", data={"id": 123})
        self.assertTrue(result.success)
        self.assertEqual(result.message, "done")
        self.assertEqual(result.data, {"id": 123})

    def test_snapshot_request_constructible(self):
        request = RuntimeSnapshotRequest(snapshot_type="lite", params={"combat_id": "abc"})
        self.assertEqual(request.snapshot_type, "lite")
        self.assertEqual(request.params, {"combat_id": "abc"})

    def test_snapshot_result_constructible(self):
        result = RuntimeSnapshotResult(success=True, data={"combatants": []})
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"combatants": []})

    def test_facade_methods_fail_closed_and_no_mutation(self):
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(command_type="test_action")
        request = RuntimeSnapshotRequest(snapshot_type="lite")

        with self.assertRaises(NotImplementedError):
            facade.submit_command(command)

        with self.assertRaises(NotImplementedError):
            facade.read_snapshot(request)

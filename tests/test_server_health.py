import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from init_tracker_server.app import create_app as package_create_app
from init_tracker_server.runtime_host import RuntimeHostState
from server_app import create_app as compat_create_app


class ServerHealthTests(unittest.TestCase):
    def _assert_app_factory_and_endpoints(self, create_app):
        # Create app via factory
        app = create_app()
        self.assertFalse(app.state.ready)
        self.assertIsNone(app.state.lan_controller)
        self.assertIsNone(app.state.runtime)
        self.assertIsNone(app.state.runtime_host)

        # Test endpoints in ready state (lifespan triggered inside TestClient context)
        with TestClient(app) as client:
            self.assertTrue(app.state.ready)

            # Test health endpoint
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "healthy", "ready": True})

            response = client.get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "healthy", "ready": True})

            # Test readiness endpoint
            response = client.get("/ready")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ready"})

            response = client.get("/api/ready")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ready"})

        # Out of the TestClient context, lifespan shutdown is triggered
        self.assertFalse(app.state.ready)
        self.assertIs(app.state.runtime_host.state, RuntimeHostState.STOPPED)

    def test_app_factory_and_endpoints(self):
        for name, create_app in (
            ("init_tracker_server.app", package_create_app),
            ("server_app", compat_create_app),
        ):
            with self.subTest(factory=name):
                self._assert_app_factory_and_endpoints(create_app)

    def test_server_app_create_app_reexports_package_factory(self):
        self.assertIs(compat_create_app, package_create_app)

    def test_unready_endpoints(self):
        for name, create_app in (
            ("init_tracker_server.app", package_create_app),
            ("server_app", compat_create_app),
        ):
            with self.subTest(factory=name):
                app = create_app()
                # Direct TestClient instantiation without 'with' statement doesn't trigger lifespan
                client = TestClient(app)

                response = client.get("/health")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "healthy", "ready": False})

                response = client.get("/ready")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"status": "not ready"})

    def test_readiness_remains_false_when_runtime_startup_fails(self):
        startup_error = RuntimeError("startup failed")

        class FailingRuntime:
            def __init__(self, *, lan_controller):
                self.lan_controller = lan_controller
                self.start_calls = 0
                self.shutdown_calls = 0

            def start(self):
                self.start_calls += 1
                raise startup_error

            def shutdown(self):
                self.shutdown_calls += 1

        with patch(
            "init_tracker_server.app.ServerRuntimeFacade",
            FailingRuntime,
        ):
            app = package_create_app(lan_controller=object())
            with self.assertRaises(RuntimeError) as raised:
                with TestClient(app):
                    self.fail("failed startup must not enter the serving lifespan")

        self.assertIs(raised.exception, startup_error)
        self.assertFalse(app.state.ready)
        self.assertIs(app.state.runtime_host.state, RuntimeHostState.FAILED)
        self.assertEqual(app.state.runtime.start_calls, 1)
        self.assertEqual(app.state.runtime.shutdown_calls, 1)

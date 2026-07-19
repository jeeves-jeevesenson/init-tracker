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

    def test_readiness_is_published_only_after_package_warm_up(self):
        events = []

        class RecordingController:
            def warm_up(self, runtime):
                events.append(("warm_up", app.state.ready, app.state.runtime_host.state))
                self.runtime = runtime

        class RecordingRuntime:
            def __init__(self, *, lan_controller):
                self.lan_controller = lan_controller
                events.append(("construct", app.state.ready, None))

            def start(self):
                events.append(("start", app.state.ready, app.state.runtime_host.state))

            def shutdown(self):
                events.append(("shutdown", app.state.ready, app.state.runtime_host.state))

        controller = RecordingController()
        app = package_create_app(lan_controller=controller)
        with patch("init_tracker_server.app.ServerRuntimeFacade", RecordingRuntime):
            with TestClient(app):
                events.append(("serving", app.state.ready, app.state.runtime_host.state))

        self.assertIs(controller.runtime, app.state.runtime)
        self.assertEqual(
            events,
            [
                ("construct", False, None),
                ("start", False, RuntimeHostState.STARTING),
                ("warm_up", False, RuntimeHostState.WARMING_UP),
                ("serving", True, RuntimeHostState.RUNNING),
                ("shutdown", False, RuntimeHostState.STOPPING),
            ],
        )

    def test_package_startup_failure_matrix_preserves_error_and_cleanup_ownership(self):
        for failed_stage, expected_events in (
            ("construct", ["construct"]),
            ("start", ["construct", "start", "shutdown"]),
            ("warm_up", ["construct", "start", "warm_up", "shutdown"]),
        ):
            with self.subTest(failed_stage=failed_stage):
                original_error = RuntimeError(f"{failed_stage} failed")
                events = []

                class FailingController:
                    def warm_up(self, runtime):
                        events.append("warm_up")
                        if failed_stage == "warm_up":
                            raise original_error

                class FailingRuntime:
                    def __init__(self, *, lan_controller):
                        events.append("construct")
                        if failed_stage == "construct":
                            raise original_error

                    def start(self):
                        events.append("start")
                        if failed_stage == "start":
                            raise original_error

                    def shutdown(self):
                        events.append("shutdown")

                app = package_create_app(lan_controller=FailingController())
                with patch("init_tracker_server.app.ServerRuntimeFacade", FailingRuntime):
                    with self.assertRaises(RuntimeError) as raised:
                        with TestClient(app):
                            self.fail("failed startup must not publish readiness")

                self.assertIs(raised.exception, original_error)
                self.assertFalse(app.state.ready)
                self.assertIs(app.state.runtime_host.state, RuntimeHostState.FAILED)
                self.assertEqual(events, expected_events)

    def test_warm_up_cleanup_failure_does_not_replace_original_error_or_retry_cleanup(self):
        warm_up_error = RuntimeError("warm-up failed")
        cleanup_error = RuntimeError("cleanup failed")
        events = []

        class FailingController:
            def warm_up(self, runtime):
                events.append("warm_up")
                raise warm_up_error

        class FailingRuntime:
            def __init__(self, *, lan_controller):
                events.append("construct")

            def start(self):
                events.append("start")

            def shutdown(self):
                events.append("shutdown")
                raise cleanup_error

        app = package_create_app(lan_controller=FailingController())
        with patch("init_tracker_server.app.ServerRuntimeFacade", FailingRuntime):
            with self.assertRaises(RuntimeError) as raised:
                with TestClient(app):
                    self.fail("failed warm-up must not publish readiness")

        self.assertIs(raised.exception, warm_up_error)
        self.assertFalse(app.state.ready)
        self.assertIs(app.state.runtime_host.state, RuntimeHostState.FAILED)
        self.assertIs(app.state.runtime_host.runtime, app.state.runtime)
        self.assertEqual(events, ["construct", "start", "warm_up", "shutdown"])

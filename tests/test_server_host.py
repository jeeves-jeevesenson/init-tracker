from __future__ import annotations

import sys
import threading
import types
import unittest
from unittest.mock import patch

import init_tracker_server.host as host_module
from init_tracker_server.host import (
    UvicornServerHost,
    UvicornServerHostRuntimeError,
    UvicornServerHostTimeoutError,
)


class FakeLoop:
    def __init__(self) -> None:
        self.ran_until_complete = None

    def run_until_complete(self, value):
        self.ran_until_complete = value


class FakeThread:
    instances = []

    def __init__(self, *, target, name, daemon) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False
        self.joined = False
        self.join_calls = []
        FakeThread.instances.append(self)

    def start(self) -> None:
        self.started = True
        self.target()

    def is_alive(self) -> bool:
        return self.started and not self.joined

    def join(self, timeout=None) -> None:
        self.join_calls.append(timeout)
        self.joined = True


class ServerHostTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeThread.instances = []

        self.configs = []
        self.servers = []

        configs = self.configs
        servers = self.servers

        class FakeConfig:
            def __init__(self, app, **kwargs) -> None:
                self.app = app
                self.kwargs = kwargs
                configs.append(self)

        class FakeServer:
            def __init__(self, config) -> None:
                self.config = config
                self._should_exit = False
                self.should_exit_assignments = []
                self.serve_calls = 0
                servers.append(self)

            @property
            def should_exit(self):
                return self._should_exit

            @should_exit.setter
            def should_exit(self, value):
                self.should_exit_assignments.append(value)
                self._should_exit = value

            def serve(self):
                self.serve_calls += 1
                return "serve-result"

        self.fake_uvicorn = types.SimpleNamespace(Config=FakeConfig, Server=FakeServer)

    def test_start_builds_uvicorn_server_loop_and_daemon_thread(self):
        app = object()
        loop = FakeLoop()
        set_event_loops = []
        ready_calls = []

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop", side_effect=set_event_loops.append),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(
                app,
                host="127.0.0.1",
                port=18801,
                on_server_ready=lambda ready_loop, server: ready_calls.append((ready_loop, server)),
            )

            thread = server_host.start()

        self.assertIs(thread, server_host.thread)
        self.assertEqual(thread.name, "InitTrackerLAN")
        self.assertTrue(thread.daemon)
        self.assertTrue(thread.started)
        self.assertEqual(set_event_loops, [loop])

        self.assertEqual(len(self.configs), 1)
        config = self.configs[0]
        self.assertIs(config.app, app)
        self.assertEqual(
            config.kwargs,
            {
                "host": "127.0.0.1",
                "port": 18801,
                "log_level": "warning",
                "access_log": False,
            },
        )

        self.assertEqual(len(self.servers), 1)
        server = self.servers[0]
        self.assertIs(server_host.loop, loop)
        self.assertIs(server_host.server, server)
        self.assertEqual(ready_calls, [(loop, server)])
        self.assertEqual(server.serve_calls, 1)
        self.assertEqual(loop.ran_until_complete, "serve-result")

    def test_wait_until_ready_observes_registered_lifespan_probe(self):
        loop = FakeLoop()
        ready = {"value": False}

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(
                object(),
                host="127.0.0.1",
                port=18801,
                ready_check=lambda: ready["value"],
                on_server_ready=lambda _loop, _server: ready.update(value=True),
            )
            server_host.start()
            server_host.wait_until_ready(timeout=0.25)

        self.assertTrue(ready["value"])
        self.assertIsNone(server_host.last_error)

    def test_start_reuses_existing_live_thread(self):
        app = object()
        loop = FakeLoop()

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(app, host="127.0.0.1", port=18801)

            first_thread = server_host.start()
            second_thread = server_host.start()

        self.assertIs(second_thread, first_thread)
        self.assertEqual(len(FakeThread.instances), 1)
        self.assertEqual(len(self.configs), 1)
        self.assertEqual(len(self.servers), 1)

    def test_concurrent_start_creates_exactly_one_worker(self):
        loop = FakeLoop()
        import_barrier = threading.Barrier(2)
        real_import = __import__
        real_thread_type = threading.Thread
        results = []
        errors = []

        class DeferredFakeThread(FakeThread):
            def start(self) -> None:
                self.started = True

        def synchronized_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "uvicorn":
                import_barrier.wait(timeout=1)
                return self.fake_uvicorn
            return real_import(name, globals, locals, fromlist, level)

        with (
            patch("builtins.__import__", side_effect=synchronized_import),
            patch.object(host_module.threading, "Thread", DeferredFakeThread),
        ):
            server_host = UvicornServerHost(object(), host="127.0.0.1", port=18801)

            def call_start():
                try:
                    results.append(server_host.start())
                except BaseException as error:
                    errors.append(error)

            callers = [real_thread_type(target=call_start) for _ in range(2)]
            for caller in callers:
                caller.start()
            for caller in callers:
                caller.join(timeout=1)
                self.assertFalse(caller.is_alive())

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], results[1])
        self.assertIs(server_host.thread, results[0])
        self.assertEqual(len(FakeThread.instances), 1)
        self.assertEqual(len(self.configs), 0)
        self.assertEqual(len(self.servers), 0)

    def test_start_reuses_completed_worker_without_restarting_lifecycle(self):
        loop = FakeLoop()

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(object(), host="127.0.0.1", port=18801)
            first_thread = server_host.start()
            server_host.wait(timeout=0.5)
            repeated_thread = server_host.start()

        self.assertIs(repeated_thread, first_thread)
        self.assertFalse(first_thread.is_alive())
        self.assertEqual(first_thread.join_calls, [0.5])
        self.assertEqual(len(FakeThread.instances), 1)
        self.assertEqual(len(self.configs), 1)
        self.assertEqual(len(self.servers), 1)
        self.assertEqual(self.servers[0].serve_calls, 1)

    def test_stop_requests_once_and_joins_worker_with_bound(self):
        loop = FakeLoop()

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(object(), host="127.0.0.1", port=18801)
            server_host.start()

            server = self.servers[0]
            self.assertFalse(server.should_exit)
            server_host.stop(timeout=0.25)

        self.assertTrue(server.should_exit)
        self.assertTrue(server_host.stop_requested)
        self.assertTrue(server_host.stop_signal_delivered)
        self.assertEqual(server.should_exit_assignments, [True])
        self.assertEqual(server_host.thread.join_calls, [0.25])
        self.assertIsNone(server_host.last_error)

    def test_duplicate_stop_delivers_one_server_signal(self):
        loop = FakeLoop()

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(object(), host="127.0.0.1", port=18801)
            server_host.start()
            self.assertTrue(server_host.request_stop())
            self.assertFalse(server_host.request_stop())
            server_host.stop(timeout=0.5)

        self.assertEqual(self.servers[0].should_exit_assignments, [True])
        self.assertEqual(server_host.thread.join_calls, [0.5])

    def test_stop_during_startup_is_latched_until_server_exists(self):
        loop = FakeLoop()

        class DeferredFakeThread(FakeThread):
            def start(self) -> None:
                self.started = True

            def run_target(self) -> None:
                self.target()

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", DeferredFakeThread),
        ):
            server_host = UvicornServerHost(object(), host="127.0.0.1", port=18801)
            thread = server_host.start()
            self.assertIsNone(server_host.server)
            self.assertTrue(server_host.request_stop())
            thread.run_target()

        self.assertTrue(self.servers[0].should_exit)
        self.assertEqual(self.servers[0].should_exit_assignments, [True])

    def test_join_timeout_is_observable_with_live_worker_reference(self):
        loop = FakeLoop()

        class HangingFakeThread(FakeThread):
            def join(self, timeout=None) -> None:
                self.join_calls.append(timeout)

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", HangingFakeThread),
        ):
            server_host = UvicornServerHost(object(), host="127.0.0.1", port=18801)
            server_host.start()
            with self.assertRaisesRegex(
                UvicornServerHostTimeoutError,
                "did not stop within 0.125 seconds",
            ) as raised:
                server_host.stop(timeout=0.125)

        self.assertIs(server_host.last_error, raised.exception)
        self.assertTrue(server_host.thread.is_alive())
        self.assertEqual(server_host.thread.join_calls, [0.125])

    def test_worker_runtime_failure_is_raised_by_bounded_wait(self):
        loop = FakeLoop()
        runtime_error = RuntimeError("serve failed")
        servers = self.servers

        class FailingServer:
            def __init__(self, config) -> None:
                self.config = config
                self.should_exit = False
                servers.append(self)

            def serve(self):
                raise runtime_error

        failing_uvicorn = types.SimpleNamespace(
            Config=self.fake_uvicorn.Config,
            Server=FailingServer,
        )
        with (
            patch.dict(sys.modules, {"uvicorn": failing_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(
                object(),
                host="127.0.0.1",
                port=18801,
                ready_check=lambda: False,
            )
            server_host.start()
            with self.assertRaises(UvicornServerHostRuntimeError) as readiness_error:
                server_host.wait_until_ready(timeout=0.5)
            with self.assertRaises(UvicornServerHostRuntimeError) as raised:
                server_host.wait(timeout=0.5)

        self.assertIs(readiness_error.exception.__cause__, runtime_error)
        self.assertIs(raised.exception.__cause__, runtime_error)
        self.assertIs(server_host.last_error, runtime_error)


if __name__ == "__main__":
    unittest.main()

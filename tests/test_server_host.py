from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import init_tracker_server.host as host_module
from init_tracker_server.host import UvicornServerHost


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
        FakeThread.instances.append(self)

    def start(self) -> None:
        self.started = True
        self.target()

    def is_alive(self) -> bool:
        return self.started


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
                self.should_exit = False
                self.serve_calls = 0
                servers.append(self)

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

    def test_request_stop_sets_existing_server_should_exit(self):
        app = object()
        loop = FakeLoop()

        with (
            patch.dict(sys.modules, {"uvicorn": self.fake_uvicorn}),
            patch.object(host_module.asyncio, "new_event_loop", return_value=loop),
            patch.object(host_module.asyncio, "set_event_loop"),
            patch.object(host_module.threading, "Thread", FakeThread),
        ):
            server_host = UvicornServerHost(app, host="127.0.0.1", port=18801)
            server_host.request_stop()
            server_host.start()

            server = self.servers[0]
            self.assertFalse(server.should_exit)
            server_host.request_stop()

        self.assertTrue(server.should_exit)


if __name__ == "__main__":
    unittest.main()

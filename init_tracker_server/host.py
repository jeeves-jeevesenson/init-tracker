from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional


ServerReadyCallback = Callable[[asyncio.AbstractEventLoop, Any], None]


class UvicornServerHost:
    """Own the Uvicorn server/thread mechanics for a registered ASGI app."""

    def __init__(
        self,
        app: Any,
        *,
        host: str,
        port: int,
        log_level: str = "warning",
        access_log: bool = False,
        thread_name: str = "InitTrackerLAN",
        on_server_ready: Optional[ServerReadyCallback] = None,
    ) -> None:
        self.app = app
        self.host = host
        self.port = port
        self.log_level = log_level
        self.access_log = access_log
        self.thread_name = thread_name
        self._on_server_ready = on_server_ready
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    @property
    def server(self) -> Optional[Any]:
        return self._server

    @property
    def thread(self) -> Optional[threading.Thread]:
        return self._thread

    def start(self) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread

        import uvicorn

        def run_server() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                log_level=self.log_level,
                access_log=self.access_log,
            )
            server = uvicorn.Server(config)
            self._server = server
            if self._on_server_ready is not None:
                self._on_server_ready(loop, server)
            loop.run_until_complete(server.serve())

        self._thread = threading.Thread(target=run_server, name=self.thread_name, daemon=True)
        self._thread.start()
        return self._thread

    def request_stop(self) -> None:
        if self._server is not None:
            try:
                self._server.should_exit = True
            except Exception:
                pass

from __future__ import annotations

import asyncio
import math
import threading
import time
from typing import Any, Callable, Optional


ServerReadyCallback = Callable[[asyncio.AbstractEventLoop, Any], None]
ServerReadinessCheck = Callable[[], bool]


class UvicornServerHostError(RuntimeError):
    """Base error raised while observing the hosted Uvicorn worker."""


class UvicornServerHostTimeoutError(TimeoutError, UvicornServerHostError):
    """Raised when the hosted Uvicorn worker does not stop within its bound."""


class UvicornServerHostRuntimeError(UvicornServerHostError):
    """Raised when the hosted Uvicorn worker fails."""


class UvicornServerHost:
    """Own one Uvicorn server/thread lifecycle for a registered ASGI app."""

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
        ready_check: Optional[ServerReadinessCheck] = None,
    ) -> None:
        self.app = app
        self.host = host
        self.port = port
        self.log_level = log_level
        self.access_log = access_log
        self.thread_name = thread_name
        self._on_server_ready = on_server_ready
        self._ready_check = ready_check
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._stop_requested = False
        self._stop_signal_delivered = False
        self._runtime_error: Optional[BaseException] = None
        self._wait_error: Optional[BaseException] = None
        self._worker_finished = threading.Event()

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    @property
    def server(self) -> Optional[Any]:
        return self._server

    @property
    def thread(self) -> Optional[threading.Thread]:
        return self._thread

    @property
    def stop_requested(self) -> bool:
        with self._lock:
            return self._stop_requested

    @property
    def stop_signal_delivered(self) -> bool:
        with self._lock:
            return self._stop_signal_delivered

    @property
    def last_error(self) -> Optional[BaseException]:
        with self._lock:
            return self._runtime_error or self._wait_error

    def start(self) -> threading.Thread:
        import uvicorn

        with self._lock:
            if self._thread is not None:
                return self._thread

            def run_server() -> None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    with self._lock:
                        self._loop = loop

                    config = uvicorn.Config(
                        self.app,
                        host=self.host,
                        port=self.port,
                        log_level=self.log_level,
                        access_log=self.access_log,
                    )
                    server = uvicorn.Server(config)
                    with self._lock:
                        self._server = server
                        self._deliver_stop_request_locked()
                    if self._on_server_ready is not None:
                        self._on_server_ready(loop, server)
                    loop.run_until_complete(server.serve())
                except BaseException as runtime_error:
                    with self._lock:
                        self._runtime_error = runtime_error
                finally:
                    self._worker_finished.set()

            thread = threading.Thread(
                target=run_server,
                name=self.thread_name,
                daemon=True,
            )
            self._thread = thread
            thread.start()
            return thread

    def wait_until_ready(self, timeout: float) -> None:
        """Wait until the registered ASGI lifespan publishes readiness."""
        timeout = self._validate_timeout(timeout)
        ready_check = self._ready_check
        if ready_check is None:
            error = UvicornServerHostError(
                "Uvicorn server readiness is not configured"
            )
            with self._lock:
                self._wait_error = error
            raise error

        deadline = time.monotonic() + timeout
        while True:
            try:
                if ready_check():
                    return
            except BaseException as readiness_error:
                error = UvicornServerHostRuntimeError(
                    "Uvicorn server readiness check failed"
                )
                with self._lock:
                    self._wait_error = error
                raise error from readiness_error

            with self._lock:
                thread = self._thread
                runtime_error = self._runtime_error

            if runtime_error is not None:
                error = UvicornServerHostRuntimeError(
                    "Uvicorn worker failed before readiness"
                )
                with self._lock:
                    self._wait_error = error
                raise error from runtime_error
            if thread is None:
                error = UvicornServerHostError(
                    "Uvicorn worker has not been started"
                )
                with self._lock:
                    self._wait_error = error
                raise error
            if self._worker_finished.is_set():
                error = UvicornServerHostRuntimeError(
                    "Uvicorn worker stopped before readiness"
                )
                with self._lock:
                    self._wait_error = error
                raise error

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = UvicornServerHostTimeoutError(
                    f"Uvicorn server did not become ready within {timeout:g} seconds"
                )
                with self._lock:
                    self._wait_error = error
                raise error
            time.sleep(min(remaining, 0.05))

    def request_stop(self) -> bool:
        """Latch and deliver the server stop signal at most once."""
        with self._lock:
            first_request = not self._stop_requested
            if first_request:
                self._stop_requested = True
                self._deliver_stop_request_locked()
            return first_request

    def wait(self, timeout: float) -> None:
        """Wait up to ``timeout`` seconds and surface timeout/worker failure."""
        timeout = self._validate_timeout(timeout)
        with self._lock:
            thread = self._thread
        if thread is None:
            return
        if thread is threading.current_thread():
            raise UvicornServerHostError(
                "cannot join the Uvicorn worker from its own thread"
            )

        thread.join(timeout=timeout)
        if thread.is_alive():
            wait_error = UvicornServerHostTimeoutError(
                f"Uvicorn worker did not stop within {timeout:g} seconds"
            )
            with self._lock:
                self._wait_error = wait_error
            raise wait_error

        with self._lock:
            runtime_error = self._runtime_error
        if runtime_error is not None:
            raise UvicornServerHostRuntimeError(
                "Uvicorn worker failed"
            ) from runtime_error

    def stop(self, timeout: float) -> None:
        """Request exactly one stop and wait a bounded time for completion."""
        self.request_stop()
        self.wait(timeout)

    def _deliver_stop_request_locked(self) -> None:
        if (
            not self._stop_requested
            or self._server is None
            or self._stop_signal_delivered
        ):
            return
        try:
            self._server.should_exit = True
        except BaseException as stop_error:
            self._runtime_error = stop_error
        finally:
            self._stop_signal_delivered = True

    @staticmethod
    def _validate_timeout(timeout: float) -> float:
        try:
            value = float(timeout)
        except (TypeError, ValueError) as error:
            raise ValueError("timeout must be a finite non-negative number") from error
        if not math.isfinite(value) or value < 0:
            raise ValueError("timeout must be a finite non-negative number")
        return value


__all__ = [
    "UvicornServerHost",
    "UvicornServerHostError",
    "UvicornServerHostRuntimeError",
    "UvicornServerHostTimeoutError",
]

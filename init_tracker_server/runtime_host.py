"""Explicit lifecycle contract for hosting a package runtime.

This module deliberately provides only an adapter boundary.  Wiring the adapter
to a process entry point or an ASGI lifespan remains the caller's responsibility.
"""

from __future__ import annotations

from enum import Enum
import math
from threading import Condition, Event, RLock, Thread, current_thread
import time
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar, runtime_checkable


RuntimeT = TypeVar("RuntimeT")
RuntimeT_co = TypeVar("RuntimeT_co", covariant=True)


class RuntimeHostState(str, Enum):
    """Observable states of a runtime host lifecycle."""

    NEW = "new"
    STARTING = "starting"
    WARMING_UP = "warming_up"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class RuntimeHostLifecycleError(RuntimeError):
    """Raised when an operation conflicts with the current lifecycle state."""


class RuntimeHostStopTimeoutError(TimeoutError, RuntimeHostLifecycleError):
    """Raised when runtime stop does not complete within its wait bound."""


@runtime_checkable
class RuntimeHost(Protocol[RuntimeT_co]):
    """Contract consumed by code that hosts a runtime explicitly."""

    @property
    def state(self) -> RuntimeHostState:
        """Return the current lifecycle state."""

    @property
    def runtime(self) -> Optional[RuntimeT_co]:
        """Return the current runtime, if one has been created."""

    @property
    def last_error(self) -> Optional[BaseException]:
        """Return the most recent lifecycle error, if any."""

    def start(self) -> RuntimeT_co:
        """Start the host and return its runtime."""

    def stop(self, timeout: float = 5.0) -> None:
        """Request stop once and wait a bounded time for completion."""


class RuntimeHostAdapter(Generic[RuntimeT]):
    """Adapt injected runtime construction/start/stop hooks to ``RuntimeHost``.

    Each adapter is a one-shot lifecycle: its factory, startup hook, and optional
    warm-up hook are each called at most once.  Duplicate and concurrent
    ``start`` calls share the first startup attempt, returning the same runtime
    on success or observing the same error on failure.  Start or warm-up failure
    triggers best-effort rollback.  Shutdown is requested at most once and runs
    on an observable worker so every caller waits only for a bounded interval.
    """

    def __init__(
        self,
        runtime_factory: Callable[[], RuntimeT],
        *,
        start_runtime: Callable[[RuntimeT], None],
        warm_up_runtime: Optional[Callable[[RuntimeT], None]] = None,
        stop_runtime: Callable[[RuntimeT], None],
    ) -> None:
        if not callable(runtime_factory):
            raise TypeError("runtime_factory must be callable")
        if not callable(start_runtime):
            raise TypeError("start_runtime must be callable")
        if warm_up_runtime is not None and not callable(warm_up_runtime):
            raise TypeError("warm_up_runtime must be callable")
        if not callable(stop_runtime):
            raise TypeError("stop_runtime must be callable")

        self._runtime_factory = runtime_factory
        self._start_runtime = start_runtime
        self._warm_up_runtime = warm_up_runtime
        self._stop_runtime = stop_runtime
        self._state = RuntimeHostState.NEW
        self._runtime: Optional[RuntimeT] = None
        self._last_error: Optional[BaseException] = None
        self._startup_error: Optional[BaseException] = None
        self._start_attempted = False
        self._stop_requested = False
        self._stop_invoked = False
        self._stop_thread: Optional[Thread] = None
        self._stop_error: Optional[BaseException] = None
        self._stop_timed_out = False
        self._lock = RLock()
        self._condition = Condition(self._lock)

    @property
    def state(self) -> RuntimeHostState:
        with self._lock:
            return self._state

    @property
    def runtime(self) -> Optional[RuntimeT]:
        with self._lock:
            return self._runtime

    @property
    def last_error(self) -> Optional[BaseException]:
        with self._lock:
            return self._last_error

    @property
    def stop_requested(self) -> bool:
        with self._lock:
            return self._stop_requested

    @property
    def stop_thread(self) -> Optional[Thread]:
        with self._lock:
            return self._stop_thread

    @property
    def stop_timed_out(self) -> bool:
        with self._lock:
            return self._stop_timed_out

    def start(self) -> RuntimeT:
        with self._condition:
            while self._state in (
                RuntimeHostState.STARTING,
                RuntimeHostState.WARMING_UP,
            ):
                self._condition.wait()

            if self._state is RuntimeHostState.RUNNING:
                runtime = self._runtime
                if runtime is None:  # Defensive invariant check.
                    raise RuntimeHostLifecycleError(
                        "running host does not have a runtime"
                    )
                return runtime
            if self._state is RuntimeHostState.STOPPING:
                raise RuntimeHostLifecycleError(
                    f"cannot start runtime host while it is {self._state.value}"
                )
            if self._state is RuntimeHostState.STOPPED:
                raise RuntimeHostLifecycleError(
                    "cannot restart a stopped runtime host lifecycle"
                )
            if self._startup_error is not None:
                raise self._startup_error
            if self._start_attempted:
                raise RuntimeHostLifecycleError(
                    "runtime host lifecycle startup was already attempted"
                )
            if self._runtime is not None:
                raise RuntimeHostLifecycleError(
                    "cannot start runtime host while a failed runtime still requires stop"
                )
            self._start_attempted = True
            self._state = RuntimeHostState.STARTING
            self._last_error = None

        runtime: Optional[RuntimeT] = None
        start_attempted = False
        try:
            runtime = self._runtime_factory()
            if runtime is None:
                raise RuntimeHostLifecycleError("runtime_factory returned None")
            start_attempted = True
            self._start_runtime(runtime)
            with self._condition:
                self._runtime = runtime
                self._state = RuntimeHostState.WARMING_UP
                self._condition.notify_all()
            if self._warm_up_runtime is not None:
                self._warm_up_runtime(runtime)
        except BaseException as start_error:
            retained_runtime: Optional[RuntimeT] = None
            if runtime is not None and start_attempted:
                with self._condition:
                    self._runtime = runtime
                    self._state = RuntimeHostState.STOPPING
                    self._stop_requested = True
                    self._stop_invoked = True
                try:
                    self._stop_runtime(runtime)
                except BaseException as rollback_error:
                    retained_runtime = runtime
                    self._stop_error = rollback_error
                    if hasattr(start_error, "add_note"):
                        start_error.add_note(
                            "runtime startup rollback failed with "
                            f"{type(rollback_error).__name__}: {rollback_error}"
                        )
            with self._condition:
                self._runtime = retained_runtime
                self._last_error = start_error
                self._startup_error = start_error
                self._state = RuntimeHostState.FAILED
                self._condition.notify_all()
            raise

        with self._condition:
            if self._stop_requested:
                self._state = RuntimeHostState.STOPPING
                self._begin_stop_locked(runtime)
            else:
                self._state = RuntimeHostState.RUNNING
            self._condition.notify_all()
            if runtime is None:  # Defensive invariant check.
                raise RuntimeHostLifecycleError(
                    "runtime host startup completed without a runtime"
                )
            return runtime

    def stop(self, timeout: float = 5.0) -> None:
        timeout = self._validate_timeout(timeout)
        deadline = time.monotonic() + timeout

        with self._condition:
            self._stop_requested = True
            while self._state in (
                RuntimeHostState.STARTING,
                RuntimeHostState.WARMING_UP,
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._record_stop_timeout_locked(timeout)
                self._condition.wait(timeout=remaining)

            if self._state is RuntimeHostState.NEW:
                self._state = RuntimeHostState.STOPPED
                self._condition.notify_all()
                return
            if self._state is RuntimeHostState.STOPPED:
                return

            runtime = self._runtime
            if runtime is None:
                return
            if not self._stop_invoked:
                self._state = RuntimeHostState.STOPPING
                self._begin_stop_locked(runtime)
            stop_thread = self._stop_thread

            if stop_thread is None:
                while self._state is RuntimeHostState.STOPPING:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise self._record_stop_timeout_locked(timeout)
                    self._condition.wait(timeout=remaining)
                self._raise_stop_error_locked()
                return

        remaining = max(0.0, deadline - time.monotonic())
        stop_thread.join(timeout=remaining)
        if stop_thread.is_alive():
            with self._condition:
                raise self._record_stop_timeout_locked(timeout)

        with self._condition:
            self._raise_stop_error_locked()

    def _begin_stop_locked(self, runtime: RuntimeT) -> None:
        if self._stop_invoked:
            return
        self._stop_invoked = True

        def stop_runtime() -> None:
            stop_error: Optional[BaseException] = None
            try:
                self._stop_runtime(runtime)
            except BaseException as error:
                stop_error = error

            with self._condition:
                self._stop_error = stop_error
                if stop_error is None:
                    self._runtime = None
                    self._state = RuntimeHostState.STOPPED
                    if not self._stop_timed_out:
                        self._last_error = None
                else:
                    self._last_error = stop_error
                    self._state = RuntimeHostState.FAILED
                self._condition.notify_all()

        self._stop_thread = Thread(
            target=stop_runtime,
            name="RuntimeHostStop",
            daemon=True,
        )
        self._stop_thread.start()

    def _record_stop_timeout_locked(
        self,
        timeout: float,
    ) -> RuntimeHostStopTimeoutError:
        timeout_error = RuntimeHostStopTimeoutError(
            f"runtime stop did not complete within {timeout:g} seconds"
        )
        self._stop_timed_out = True
        self._last_error = timeout_error
        return timeout_error

    def _raise_stop_error_locked(self) -> None:
        if self._stop_error is not None:
            raise self._stop_error

    @staticmethod
    def _validate_timeout(timeout: float) -> float:
        try:
            value = float(timeout)
        except (TypeError, ValueError) as error:
            raise ValueError("timeout must be a finite non-negative number") from error
        if not math.isfinite(value) or value < 0:
            raise ValueError("timeout must be a finite non-negative number")
        return value


class HeadlessRuntimeHost(Generic[RuntimeT]):
    """Own one headless tracker and its package-hosted server lifecycle.

    The tracker instance is constructed with its legacy scheduled LAN auto-start
    disabled by the caller.  This host then starts the existing LAN controller
    once, waits for the package ASGI lifespan to publish readiness, runs the
    headless event loop, and performs bounded server stop/join cleanup.
    """

    def __init__(
        self,
        runtime_factory: Callable[[], RuntimeT],
        *,
        prepare_runtime: Optional[Callable[[RuntimeT], None]] = None,
        auto_start_server: bool = True,
        server_ready_timeout: float = 60.0,
        server_stop_timeout: float = 5.0,
    ) -> None:
        if prepare_runtime is not None and not callable(prepare_runtime):
            raise TypeError("prepare_runtime must be callable")
        self._prepare_runtime = prepare_runtime
        self._auto_start_server = bool(auto_start_server)
        self._server_ready_timeout = RuntimeHostAdapter._validate_timeout(
            server_ready_timeout
        )
        self._server_stop_timeout = RuntimeHostAdapter._validate_timeout(
            server_stop_timeout
        )
        self._mainloop_thread: Optional[Thread] = None
        self._mainloop_entered = Event()
        self._mainloop_ready = Event()
        self._mainloop_error: Optional[BaseException] = None
        self._lifecycle = RuntimeHostAdapter(
            runtime_factory,
            start_runtime=self._start_runtime,
            warm_up_runtime=self._wait_until_ready,
            stop_runtime=self._stop_runtime,
        )

    @property
    def state(self) -> RuntimeHostState:
        return self._lifecycle.state

    @property
    def runtime(self) -> Optional[RuntimeT]:
        return self._lifecycle.runtime

    @property
    def last_error(self) -> Optional[BaseException]:
        return self._lifecycle.last_error

    @property
    def stop_thread(self) -> Optional[Thread]:
        return self._lifecycle.stop_thread

    def start(self) -> RuntimeT:
        return self._lifecycle.start()

    def run(self) -> None:
        self.start()
        mainloop_thread = self._mainloop_thread
        if mainloop_thread is None:
            error = RuntimeHostLifecycleError(
                "headless runtime mainloop was not started"
            )
            try:
                self.stop()
            except BaseException as cleanup_error:
                self._add_cleanup_note(error, cleanup_error)
            raise error

        if mainloop_thread is current_thread():
            raise RuntimeHostLifecycleError(
                "cannot join the headless runtime mainloop from its own thread"
            )
        mainloop_thread.join()
        run_error = self._mainloop_error
        if run_error is not None:
            try:
                self.stop()
            except BaseException as cleanup_error:
                self._add_cleanup_note(run_error, cleanup_error)
            raise run_error
        self.stop()

    def stop(self, timeout: float = 5.0) -> None:
        self._lifecycle.stop(timeout=timeout)

    def _start_runtime(self, runtime: RuntimeT) -> None:
        if self._prepare_runtime is not None:
            self._prepare_runtime(runtime)
        self._start_mainloop(runtime)
        if not self._auto_start_server:
            return
        lan = self._lan_controller(runtime)
        start = getattr(lan, "start", None)
        if not callable(start):
            raise RuntimeHostLifecycleError(
                "headless runtime LAN controller does not provide start()"
            )
        start(quiet=True)

    def _start_mainloop(self, runtime: RuntimeT) -> None:
        mainloop = getattr(runtime, "mainloop", None)
        if not callable(mainloop):
            raise RuntimeHostLifecycleError(
                "headless runtime does not provide mainloop()"
            )

        def run_mainloop() -> None:
            self._mainloop_entered.set()
            try:
                mainloop()
            except BaseException as error:
                self._mainloop_error = error

        mainloop_thread = Thread(
            target=run_mainloop,
            name="HeadlessRuntimeMainloop",
            daemon=True,
        )
        self._mainloop_thread = mainloop_thread
        mainloop_thread.start()
        if not self._mainloop_entered.wait(timeout=self._server_ready_timeout):
            raise RuntimeHostLifecycleError(
                "headless runtime mainloop did not start within its readiness bound"
            )

        after = getattr(runtime, "after", None)
        if callable(after):
            after(0, self._mainloop_ready.set)
        else:
            self._mainloop_ready.set()
        if not self._mainloop_ready.wait(timeout=self._server_ready_timeout):
            if self._mainloop_error is not None:
                raise self._mainloop_error
            raise RuntimeHostLifecycleError(
                "headless runtime mainloop did not process callbacks within its readiness bound"
            )
        if self._mainloop_error is not None:
            raise self._mainloop_error

    def _wait_until_ready(self, runtime: RuntimeT) -> None:
        if not self._auto_start_server:
            return
        lan = self._lan_controller(runtime)
        wait_until_ready = getattr(lan, "wait_until_ready", None)
        if not callable(wait_until_ready):
            raise RuntimeHostLifecycleError(
                "headless runtime LAN controller does not provide wait_until_ready()"
            )
        wait_until_ready(timeout=self._server_ready_timeout)

    def _stop_runtime(self, runtime: RuntimeT) -> None:
        cleanup_error: Optional[BaseException] = None
        lan = getattr(runtime, "_lan", None)
        stop_server = getattr(lan, "stop", None) if lan is not None else None
        if callable(stop_server):
            try:
                stop_server()
            except BaseException as error:
                cleanup_error = error

        join_server = getattr(lan, "join", None) if lan is not None else None
        if callable(join_server):
            try:
                join_server(timeout=self._server_stop_timeout)
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
                else:
                    self._add_cleanup_note(cleanup_error, error)

        quit_runtime = getattr(runtime, "quit", None)
        if callable(quit_runtime):
            try:
                quit_runtime()
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
                else:
                    self._add_cleanup_note(cleanup_error, error)

        mainloop_thread = self._mainloop_thread
        if mainloop_thread is not None and mainloop_thread is not current_thread():
            mainloop_thread.join(timeout=self._server_stop_timeout)
            if mainloop_thread.is_alive():
                error = RuntimeHostStopTimeoutError(
                    "headless runtime mainloop did not stop within "
                    f"{self._server_stop_timeout:g} seconds"
                )
                if cleanup_error is None:
                    cleanup_error = error
                else:
                    self._add_cleanup_note(cleanup_error, error)

        if cleanup_error is not None:
            raise cleanup_error

    @staticmethod
    def _lan_controller(runtime: RuntimeT) -> Any:
        lan = getattr(runtime, "_lan", None)
        if lan is None:
            raise RuntimeHostLifecycleError(
                "headless runtime does not provide a LAN controller"
            )
        return lan

    @staticmethod
    def _add_cleanup_note(
        primary_error: BaseException,
        cleanup_error: BaseException,
    ) -> None:
        if hasattr(primary_error, "add_note"):
            primary_error.add_note(
                "headless runtime cleanup failed with "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )


__all__ = [
    "HeadlessRuntimeHost",
    "RuntimeHost",
    "RuntimeHostAdapter",
    "RuntimeHostLifecycleError",
    "RuntimeHostStopTimeoutError",
    "RuntimeHostState",
]

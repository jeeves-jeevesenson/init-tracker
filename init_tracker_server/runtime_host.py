"""Explicit lifecycle contract for hosting a package runtime.

This module deliberately provides only an adapter boundary.  Wiring the adapter
to a process entry point or an ASGI lifespan remains the caller's responsibility.
"""

from __future__ import annotations

from enum import Enum
from threading import RLock
from typing import Callable, Generic, Optional, Protocol, TypeVar, runtime_checkable


RuntimeT = TypeVar("RuntimeT")
RuntimeT_co = TypeVar("RuntimeT_co", covariant=True)


class RuntimeHostState(str, Enum):
    """Observable states of a runtime host lifecycle."""

    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class RuntimeHostLifecycleError(RuntimeError):
    """Raised when an operation conflicts with the current lifecycle state."""


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

    def stop(self) -> None:
        """Stop the current runtime, if one is active."""


class RuntimeHostAdapter(Generic[RuntimeT]):
    """Adapt injected runtime construction/start/stop hooks to ``RuntimeHost``.

    ``start`` and ``stop`` are idempotent in their stable success states.  A
    stopped adapter can be started again, in which case the factory creates a
    fresh runtime.  Startup failure triggers best-effort rollback.  If shutdown
    fails, the runtime is retained so that a later ``stop`` call can retry it.
    """

    def __init__(
        self,
        runtime_factory: Callable[[], RuntimeT],
        *,
        start_runtime: Callable[[RuntimeT], None],
        stop_runtime: Callable[[RuntimeT], None],
    ) -> None:
        if not callable(runtime_factory):
            raise TypeError("runtime_factory must be callable")
        if not callable(start_runtime):
            raise TypeError("start_runtime must be callable")
        if not callable(stop_runtime):
            raise TypeError("stop_runtime must be callable")

        self._runtime_factory = runtime_factory
        self._start_runtime = start_runtime
        self._stop_runtime = stop_runtime
        self._state = RuntimeHostState.NEW
        self._runtime: Optional[RuntimeT] = None
        self._last_error: Optional[BaseException] = None
        self._lock = RLock()

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

    def start(self) -> RuntimeT:
        with self._lock:
            if self._state is RuntimeHostState.RUNNING:
                runtime = self._runtime
                if runtime is None:  # Defensive invariant check.
                    raise RuntimeHostLifecycleError(
                        "running host does not have a runtime"
                    )
                return runtime
            if self._state in (RuntimeHostState.STARTING, RuntimeHostState.STOPPING):
                raise RuntimeHostLifecycleError(
                    f"cannot start runtime host while it is {self._state.value}"
                )
            if self._runtime is not None:
                raise RuntimeHostLifecycleError(
                    "cannot start runtime host while a failed runtime still requires stop"
                )
            self._state = RuntimeHostState.STARTING
            self._last_error = None

        try:
            runtime = self._runtime_factory()
            if runtime is None:
                raise RuntimeHostLifecycleError("runtime_factory returned None")
            self._start_runtime(runtime)
        except BaseException as start_error:
            retained_runtime: Optional[RuntimeT] = None
            if "runtime" in locals() and runtime is not None:
                try:
                    self._stop_runtime(runtime)
                except BaseException as rollback_error:
                    retained_runtime = runtime
                    if hasattr(start_error, "add_note"):
                        start_error.add_note(
                            "runtime startup rollback failed with "
                            f"{type(rollback_error).__name__}: {rollback_error}"
                        )
            with self._lock:
                self._runtime = retained_runtime
                self._last_error = start_error
                self._state = RuntimeHostState.FAILED
            raise

        with self._lock:
            self._runtime = runtime
            self._state = RuntimeHostState.RUNNING
            return runtime

    def stop(self) -> None:
        with self._lock:
            if self._state in (RuntimeHostState.STARTING, RuntimeHostState.STOPPING):
                raise RuntimeHostLifecycleError(
                    f"cannot stop runtime host while it is {self._state.value}"
                )
            runtime = self._runtime
            if runtime is None:
                return
            self._state = RuntimeHostState.STOPPING
            self._last_error = None

        try:
            self._stop_runtime(runtime)
        except BaseException as stop_error:
            with self._lock:
                self._last_error = stop_error
                self._state = RuntimeHostState.FAILED
            raise

        with self._lock:
            self._runtime = None
            self._state = RuntimeHostState.STOPPED


__all__ = [
    "RuntimeHost",
    "RuntimeHostAdapter",
    "RuntimeHostLifecycleError",
    "RuntimeHostState",
]

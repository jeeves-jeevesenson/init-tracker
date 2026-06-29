from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RuntimeCommand:
    """Explicit contract for a mutating action submitted to the server runtime."""
    command_type: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeCommandResult:
    """Explicit result returned by the runtime command execution."""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


# Command lifecycle status constants
STATUS_ACCEPTED = "accepted"
STATUS_QUEUED = "queued"
STATUS_DISPATCHING = "dispatching"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class RuntimeCommandTrace:
    """Record of a command execution trace for observability."""
    command_type: str
    status: str
    duration_ms: float
    error_class: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeSnapshotRequest:
    """Explicit contract for requesting a read-model snapshot of runtime state."""
    snapshot_type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeSnapshotResult:
    """Explicit container for a retrieved read-model snapshot."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)


COMMAND_UPDATE_SPELL_COLOR = "update_spell_color"


class ServerRuntimeFacade:
    """Narrow facade skeleton between ASGI app and the legacy tracker runtime."""

    def __init__(self, lan_controller: Optional[Any] = None) -> None:
        self.lan_controller = lan_controller
        self._ready = False
        self.last_command_trace: Optional[RuntimeCommandTrace] = None

    def start(self) -> None:
        """Mark the runtime facade ready for ASGI request handling."""
        self._ready = True

    def shutdown(self) -> None:
        """Mark the runtime facade no longer ready."""
        self._ready = False

    def is_ready(self) -> bool:
        """Return whether the runtime facade is ready."""
        return self._ready

    def submit_command(self, command: RuntimeCommand) -> RuntimeCommandResult:
        """Submit a command to the runtime."""
        import time
        start_time = time.perf_counter()

        try:
            if command.command_type == COMMAND_UPDATE_SPELL_COLOR:
                if not self.lan_controller:
                    raise RuntimeError("LanController is not configured on the facade.")
                app = getattr(self.lan_controller, "app", None)
                if not app:
                    raise RuntimeError("InitiativeTracker app is not configured on LanController.")

                spell_id = command.payload.get("spell_id")
                color = command.payload.get("color")

                # Call the actual save function
                result = app._save_spell_color(spell_id, color)

                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=STATUS_COMPLETED,
                    duration_ms=duration_ms,
                    error_class=None
                )
                return RuntimeCommandResult(
                    success=True,
                    message="Spell color updated successfully.",
                    data={"spell": result}
                )

            raise NotImplementedError(f"Command type '{command.command_type}' is not yet implemented.")
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.last_command_trace = RuntimeCommandTrace(
                command_type=command.command_type,
                status=STATUS_FAILED,
                duration_ms=duration_ms,
                error_class=exc.__class__.__name__
            )
            raise

    def read_snapshot(self, request: RuntimeSnapshotRequest) -> RuntimeSnapshotResult:
        """Read a state snapshot from the runtime.

        Currently fails closed with NotImplementedError.
        """
        raise NotImplementedError("Snapshot reading is not yet implemented.")

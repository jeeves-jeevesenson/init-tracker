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
COMMAND_TEST_QUEUE = "test_queue_command"
COMMAND_SET_FACING = "set_facing"
COMMAND_SET_AURAS_ENABLED = "set_auras_enabled"
COMMAND_PLACE_COMBATANT = "place_combatant"
COMMAND_REMOVE_AOE = "aoe_remove"
COMMAND_MOVE_AOE = "aoe_move"
COMMAND_SET_OBSTACLE = "set_obstacle"
COMMAND_SET_TERRAIN = "set_terrain"
COMMAND_SET_ELEVATION = "set_elevation"
COMMAND_SET_MAP_SETTINGS = "set_map_settings"
COMMAND_UPSERT_MAP_BACKGROUND = "upsert_map_background"
COMMAND_REMOVE_MAP_BACKGROUND = "remove_map_background"
COMMAND_SET_MAP_BACKGROUND_ORDER = "set_map_background_order"
COMMAND_UPSERT_MAP_HAZARD = "upsert_map_hazard"
COMMAND_REMOVE_MAP_HAZARD = "remove_map_hazard"
COMMAND_UPSERT_MAP_FEATURE = "upsert_map_feature"
COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"









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

    def _submit_to_lan_queue(self, command: RuntimeCommand, timeout_ms: int = 5000) -> RuntimeCommandResult:
        """Helper to submit a command to the LanController queue and wait for completion."""
        import uuid
        import time

        if not self.lan_controller:
            raise RuntimeError("LanController is not configured on the facade.")

        action_id = f"facade-{uuid.uuid4().hex[:16]}"
        trace_id = f"trace-{uuid.uuid4().hex[:16]}"
        received_at_ns = time.perf_counter_ns()

        # Convert to the dictionary shape expected by the existing LanController._actions / _lan_apply_action flow.
        msg = {
            "type": command.command_type,
            "action_id": action_id,
            "_trace_id": trace_id,
            "_received_at_ns": received_at_ns,
            "_ws_id": None,
            "_claimed_cid": command.payload.get("cid"),
            **command.payload
        }

        # Register pending action state under lan_controller._action_states_lock
        with self.lan_controller._action_states_lock:
            self.lan_controller._action_states[action_id] = {
                "status": "pending",
                "received_at_ns": received_at_ns,
                "command": command.command_type,
                "ws_id": None,
                "cid": command.payload.get("cid")
            }
            if len(self.lan_controller._action_states) > self.lan_controller._action_history_limit:
                try:
                    oldest_key = next(iter(self.lan_controller._action_states))
                    self.lan_controller._action_states.pop(oldest_key, None)
                except Exception:
                    pass

        # Enqueue the action onto lan_controller._actions
        self.lan_controller._actions.put(msg)

        # Wait on the request thread by bounded polling of _action_states until completion or timeout
        start_wait = time.perf_counter()
        timeout_s = timeout_ms / 1000.0
        poll_interval_s = 0.005 # 5 ms
        result_state = None

        while True:
            with self.lan_controller._action_states_lock:
                state = self.lan_controller._action_states.get(action_id)
                if state and state.get("status") == "completed":
                    result_state = state
                    break

            if time.perf_counter() - start_wait >= timeout_s:
                break

            time.sleep(poll_interval_s)

        duration_ms = (time.perf_counter() - start_wait) * 1000.0
        qsize = getattr(self.lan_controller._actions, "qsize", lambda: 0)()

        metadata = {
            "queue_size": qsize,
            "action_id": action_id,
        }

        if result_state is None:
            # Timed out outcome
            self.last_command_trace = RuntimeCommandTrace(
                command_type=command.command_type,
                status=STATUS_TIMED_OUT,
                duration_ms=duration_ms,
                error_class="TimeoutError",
                metadata=metadata
            )
            raise TimeoutError(f"Command '{command.command_type}' timed out after {timeout_ms}ms")

        result = result_state.get("result") or {}
        completed_at_ns = result_state.get("completed_at_ns")
        if completed_at_ns and received_at_ns:
            metadata["queue_wait_ms"] = (completed_at_ns - received_at_ns) / 1_000_000.0

        if result.get("status") == "error":
            # Failed outcome
            reason = result.get("reason", "UnknownError")
            self.last_command_trace = RuntimeCommandTrace(
                command_type=command.command_type,
                status=STATUS_FAILED,
                duration_ms=duration_ms,
                error_class=reason,
                metadata=metadata
            )
            # Raise corresponding exception to preserve mapping
            self._raise_mapped_exception(reason)

        # Completed outcome
        self.last_command_trace = RuntimeCommandTrace(
            command_type=command.command_type,
            status=STATUS_COMPLETED,
            duration_ms=duration_ms,
            error_class=None,
            metadata=metadata
        )
        return RuntimeCommandResult(
            success=True,
            message=f"Command '{command.command_type}' completed successfully.",
            data={"result": result}
        )

    def _raise_mapped_exception(self, reason: str) -> None:
        if reason == "ValueError":
            raise ValueError("Queue command failed: ValueError")
        elif reason == "FileNotFoundError":
            raise FileNotFoundError("Queue command failed: FileNotFoundError")
        elif reason == "RuntimeError":
            raise RuntimeError("Queue command failed: RuntimeError")
        elif reason == "NotImplementedError":
            raise NotImplementedError("Queue command failed: NotImplementedError")
        else:
            raise RuntimeError(f"Queue command failed: {reason}")

    def submit_command(self, command: RuntimeCommand) -> RuntimeCommandResult:
        """Submit a command to the runtime."""
        if command.command_type == COMMAND_TEST_QUEUE:
            timeout_ms = command.payload.get("timeout_ms", 5000)
            return self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
        elif command.command_type == COMMAND_SET_FACING:
            timeout_ms = command.payload.get("timeout_ms", 5000)
            return self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
        elif command.command_type == COMMAND_SET_AURAS_ENABLED:
            timeout_ms = command.payload.get("timeout_ms", 5000)
            return self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
        elif command.command_type == COMMAND_PLACE_COMBATANT:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    place_result = state.get("place_result") if state else None

                if place_result and not place_result.get("ok"):
                    err_msg = place_result.get("error", "Cannot place combatant.")
                    if err_msg.startswith("Failed to place combatant:"):
                        raise RuntimeError(err_msg)
                    else:
                        raise ValueError(err_msg)

                return RuntimeCommandResult(
                    success=True,
                    message="Combatant placed successfully.",
                    data={"place_result": place_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_REMOVE_AOE:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    remove_result = state.get("remove_result") if state else None

                if remove_result and not remove_result.get("ok"):
                    raise ValueError(remove_result.get("error", "Cannot remove AoE."))

                if not remove_result:
                    raise RuntimeError("No remove result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="AoE removed successfully.",
                    data={"remove_result": remove_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_MOVE_AOE:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    move_result = state.get("move_result") if state else None

                if move_result and not move_result.get("ok"):
                    raise ValueError(move_result.get("error", "Cannot move AoE."))

                if not move_result:
                    raise RuntimeError("No move result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="AoE moved successfully.",
                    data={"move_result": move_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_SET_OBSTACLE:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    obstacle_result = state.get("obstacle_result") if state else None

                if obstacle_result and not obstacle_result.get("ok"):
                    raise ValueError(obstacle_result.get("error", "Cannot update obstacle."))

                if not obstacle_result:
                    raise RuntimeError("No obstacle result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Obstacle cell updated successfully.",
                    data={"obstacle_result": obstacle_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_SET_TERRAIN:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    terrain_result = state.get("terrain_result") if state else None

                if terrain_result and not terrain_result.get("ok"):
                    raise ValueError(terrain_result.get("error", "Cannot update terrain."))

                if not terrain_result:
                    raise RuntimeError("No terrain result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Terrain cell updated successfully.",
                    data={"terrain_result": terrain_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_SET_ELEVATION:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    elevation_result = state.get("elevation_result") if state else None

                if elevation_result and not elevation_result.get("ok"):
                    raise ValueError(elevation_result.get("error", "Cannot update elevation."))

                if not elevation_result:
                    raise RuntimeError("No elevation result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Elevation cell updated successfully.",
                    data={"elevation_result": elevation_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_SET_MAP_SETTINGS:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    settings_result = state.get("settings_result") if state else None

                if settings_result and not settings_result.get("ok"):
                    raise ValueError(settings_result.get("error", "Cannot update map settings."))

                if not settings_result:
                    raise RuntimeError("No settings result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map settings updated successfully.",
                    data={"settings_result": settings_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_UPSERT_MAP_BACKGROUND:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    background_result = state.get("background_result") if state else None

                if background_result and not background_result.get("ok"):
                    raise ValueError(background_result.get("error", "Cannot update background layer."))

                if not background_result:
                    raise RuntimeError("No background result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map background updated successfully.",
                    data={"background_result": background_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_REMOVE_MAP_BACKGROUND:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    remove_background_result = state.get("remove_background_result") if state else None

                if remove_background_result and not remove_background_result.get("ok"):
                    raise ValueError(remove_background_result.get("error", "Cannot remove background layer."))

                if not remove_background_result:
                    raise RuntimeError("No remove background result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map background removed successfully.",
                    data={"remove_background_result": remove_background_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_SET_MAP_BACKGROUND_ORDER:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    reorder_background_result = state.get("reorder_background_result") if state else None

                if reorder_background_result and not reorder_background_result.get("ok"):
                    raise ValueError(reorder_background_result.get("error", "Cannot reorder background layer."))

                if not reorder_background_result:
                    raise RuntimeError("No reorder background result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map background order updated successfully.",
                    data={"reorder_background_result": reorder_background_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_UPSERT_MAP_HAZARD:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    hazard_result = state.get("hazard_result") if state else None

                if hazard_result and not hazard_result.get("ok"):
                    raise ValueError(hazard_result.get("error", "Cannot update hazard."))

                if not hazard_result:
                    raise RuntimeError("No hazard result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map hazard updated successfully.",
                    data={"hazard_result": hazard_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_REMOVE_MAP_HAZARD:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    hazard_result = state.get("hazard_result") if state else None

                if hazard_result and not hazard_result.get("ok"):
                    raise ValueError(hazard_result.get("error", "Cannot remove hazard."))

                if not hazard_result:
                    raise RuntimeError("No hazard result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map hazard removed successfully.",
                    data={"hazard_result": hazard_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_UPSERT_MAP_FEATURE:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    feature_result = state.get("feature_result") if state else None

                if feature_result and not feature_result.get("ok"):
                    raise ValueError(feature_result.get("error", "Cannot update feature."))

                if not feature_result:
                    raise RuntimeError("No feature result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map feature updated successfully.",
                    data={"feature_result": feature_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise
        elif command.command_type == COMMAND_REMOVE_MAP_FEATURE:
            import time
            start_time = time.perf_counter()
            try:
                timeout_ms = command.payload.get("timeout_ms", 5000)
                res = self._submit_to_lan_queue(command, timeout_ms=timeout_ms)
                action_id = self.last_command_trace.metadata.get("action_id")
                with self.lan_controller._action_states_lock:
                    state = self.lan_controller._action_states.get(action_id)
                    feature_result = state.get("feature_result") if state else None

                if feature_result and not feature_result.get("ok"):
                    raise ValueError(feature_result.get("error", "Cannot remove feature."))

                if not feature_result:
                    raise RuntimeError("No feature result from queue.")

                return RuntimeCommandResult(
                    success=True,
                    message="Map feature removed successfully.",
                    data={"feature_result": feature_result}
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status = STATUS_TIMED_OUT if isinstance(exc, TimeoutError) else STATUS_FAILED
                self.last_command_trace = RuntimeCommandTrace(
                    command_type=command.command_type,
                    status=status,
                    duration_ms=duration_ms,
                    error_class=exc.__class__.__name__,
                    metadata=self.last_command_trace.metadata if self.last_command_trace else {}
                )
                raise







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

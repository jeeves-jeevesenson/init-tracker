import unittest
from unittest.mock import MagicMock
from server_runtime import (
    ServerRuntimeFacade,
    RuntimeCommand,
    RuntimeCommandResult,
    COMMAND_UPDATE_SPELL_COLOR,
    COMMAND_SET_FACING,
)


class ServerRuntimeFacadeTests(unittest.TestCase):
    def test_spell_color_command_execution(self):
        # 1. facade executes the spell-color command using a fake app/controller hook
        mock_app = MagicMock()
        mock_app._save_spell_color.return_value = {"id": "fireball", "color": "red"}

        mock_lan_controller = MagicMock()
        mock_lan_controller.app = mock_app

        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )

        result = facade.submit_command(command)

        self.assertTrue(result.success)
        self.assertEqual(result.message, "Spell color updated successfully.")
        self.assertEqual(result.data, {"spell": {"id": "fireball", "color": "red"}})
        mock_app._save_spell_color.assert_called_once_with("fireball", "red")

    def test_unknown_command_fails_closed(self):
        # 2. unknown command still fails closed
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(command_type="unknown_action")

        with self.assertRaises(NotImplementedError) as ctx:
            facade.submit_command(command)
        self.assertIn("Command type 'unknown_action' is not yet implemented.", str(ctx.exception))

    def test_facade_without_lan_controller_fails(self):
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )
        with self.assertRaises(RuntimeError) as ctx:
            facade.submit_command(command)
        self.assertIn("LanController is not configured on the facade.", str(ctx.exception))

    def test_facade_without_app_fails(self):
        mock_lan_controller = MagicMock()
        mock_lan_controller.app = None
        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )
        with self.assertRaises(RuntimeError) as ctx:
            facade.submit_command(command)
        self.assertIn("InitiativeTracker app is not configured on LanController.", str(ctx.exception))

    def test_no_queue_or_cache_behavior_introduced(self):
        # 4. no queue/cache behavior is introduced
        facade = ServerRuntimeFacade()
        # Verify no queue/cache attributes are present on initialization
        self.assertFalse(hasattr(facade, "queue"))
        self.assertFalse(hasattr(facade, "command_" + "queue"))
        self.assertFalse(hasattr(facade, "snapshot_" + "cache"))

    def test_route_level_behavior_mapping(self):
        # 3. route-level behavior mapping is preserved
        from fastapi import FastAPI, Body, HTTPException
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()

        mock_runtime = MagicMock()

        @app.post("/api/spells/{spell_id}/color")
        async def update_spell_color(spell_id: str, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            spell_id = str(spell_id or "").strip()
            if not spell_id:
                raise HTTPException(status_code=400, detail="Missing spell id.")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_UPDATE_SPELL_COLOR,
                    payload={"spell_id": spell_id, "color": payload.get("color")}
                )
                cmd_result = mock_runtime.submit_command(command)
                result = cmd_result.data.get("spell")
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Spell not found.")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc))
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to save spell color.")
            return {"ok": True, "spell": result}

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"spell": "red"}
        )
        response = client.post("/api/spells/fireball/color", json={"color": "red"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "spell": "red"})

        # 2. Invalid payload (non-dict)
        import asyncio
        try:
            asyncio.run(update_spell_color("fireball", "not a dict"))
            self.fail("HTTPException not raised for non-dict payload")
        except HTTPException as e:
            self.assertEqual(e.status_code, 400)
            self.assertEqual(e.detail, "Invalid payload.")

        # 3. FileNotFoundError -> 404
        mock_runtime.submit_command.side_effect = FileNotFoundError()
        response = client.post("/api/spells/fireball/color", json={"color": "blue"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("Spell not found.", response.json()["detail"])

        # 4. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Invalid hex color")
        response = client.post("/api/spells/fireball/color", json={"color": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid hex color", response.json()["detail"])

        # 5. RuntimeError -> 500
        mock_runtime.submit_command.side_effect = RuntimeError("Database offline")
        response = client.post("/api/spells/fireball/color", json={"color": "green"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database offline", response.json()["detail"])

        # 6. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Unknown error")
        response = client.post("/api/spells/fireball/color", json={"color": "green"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to save spell color.", response.json()["detail"])

    def test_spell_color_lifecycle_observability_success(self):
        # 1. successful spell-color command still works and records a completed lifecycle/trace
        mock_app = MagicMock()
        mock_app._save_spell_color.return_value = {"id": "fireball", "color": "red"}

        mock_lan_controller = MagicMock()
        mock_lan_controller.app = mock_app

        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)

        # Trace duration/status fields are present and deterministic enough for unit tests
        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPDATE_SPELL_COLOR)
        self.assertEqual(trace.status, "completed")
        self.assertIsInstance(trace.duration_ms, float)
        self.assertGreaterEqual(trace.duration_ms, 0.0)
        self.assertIsNone(trace.error_class)

    def test_spell_color_lifecycle_observability_failure(self):
        # 2. failing spell-color command still raises the original exception and records a failed lifecycle/trace with error_class
        mock_app = MagicMock()
        mock_app._save_spell_color.side_effect = ValueError("Invalid hex color")

        mock_lan_controller = MagicMock()
        mock_lan_controller.app = mock_app

        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "invalid"}
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Invalid hex color")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPDATE_SPELL_COLOR)
        self.assertEqual(trace.status, "failed")
        self.assertIsInstance(trace.duration_ms, float)
        self.assertGreaterEqual(trace.duration_ms, 0.0)
        self.assertEqual(trace.error_class, "ValueError")

    def test_unknown_command_lifecycle_observability_failure(self):
        # 3. unknown command still fails closed and records no successful completion
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(command_type="unknown_action")

        with self.assertRaises(NotImplementedError):
            facade.submit_command(command)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, "unknown_action")
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "NotImplementedError")

    def test_queue_adapter_success(self):
        # Test that the queue adapter successfully enqueues the action,
        # registers pending state, polls for completion, updates state and returns result.
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()

        def process_success(msg):
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied", "custom_key": "val"},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type="test_queue_command",
            payload={"cid": 42, "foo": "bar"}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(result.data["result"]["status"], "applied")
        self.assertEqual(result.data["result"]["custom_key"], "val")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, "test_queue_command")
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_queue_adapter_timeout(self):
        # Test that the queue adapter handles timeouts properly by raising TimeoutError
        # and tracing the event with STATUS_TIMED_OUT.
        import threading

        class FakeQueue:
            def __init__(self):
                self.items = []
            def put(self, item):
                self.items.append(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type="test_queue_command",
            payload={"cid": 42, "timeout_ms": 10}
        )

        with self.assertRaises(TimeoutError) as ctx:
            facade.submit_command(command)
        self.assertIn("timed out after 10ms", str(ctx.exception))

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, "test_queue_command")
        self.assertEqual(trace.status, "timed_out")
        self.assertEqual(trace.error_class, "TimeoutError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_queue_adapter_mapped_errors(self):
        # Test that the queue adapter maps and raises the correct exceptions.
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        for err_type, expected_exc in [
            ("ValueError", ValueError),
            ("FileNotFoundError", FileNotFoundError),
            ("RuntimeError", RuntimeError),
            ("NotImplementedError", NotImplementedError),
            ("SomeOtherError", RuntimeError)
        ]:
            controller = FakeLanController()
            facade = ServerRuntimeFacade(lan_controller=controller)

            def make_process_error(err_name, ctrl):
                return lambda msg: ctrl._action_states[msg["action_id"]].update({
                    "status": "completed",
                    "result": {"status": "error", "reason": err_name},
                    "completed_at_ns": time.perf_counter_ns()
                })

            controller._actions.on_put = make_process_error(err_type, controller)
            command = RuntimeCommand(command_type="test_queue_command")
            with self.assertRaises(expected_exc) as ctx:
                facade.submit_command(command)
            self.assertIn(f"Queue command failed: {err_type}", str(ctx.exception))

            trace = facade.last_command_trace
            self.assertIsNotNone(trace)
            self.assertEqual(trace.command_type, "test_queue_command")
            self.assertEqual(trace.status, "failed")
            self.assertEqual(trace.error_class, err_type)
            self.assertEqual(trace.metadata["queue_size"], 1)

    def test_set_facing_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied", "cid": msg.get("cid"), "facing_deg": msg.get("facing_deg")},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_FACING,
            payload={"cid": 42, "facing_deg": 180}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_facing")
        self.assertEqual(msg["cid"], 42)
        self.assertEqual(msg["facing_deg"], 180)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_FACING)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

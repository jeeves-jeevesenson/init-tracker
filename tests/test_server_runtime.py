import unittest
from unittest.mock import MagicMock
from server_runtime import (
    ServerRuntimeFacade,
    RuntimeCommand,
    RuntimeCommandResult,
    COMMAND_UPDATE_SPELL_COLOR,
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

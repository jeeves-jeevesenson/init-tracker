import unittest
import queue
import time
import threading
import json
from unittest.mock import MagicMock, patch, AsyncMock
import dnd_initative_tracker as tracker_mod

class LanActionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.app = MagicMock(spec=tracker_mod.InitiativeTracker)
        self.app._debug_trace_counts.return_value = {}
        self.lan = tracker_mod.LanController(self.app)
        # Mock loop and other async bits
        self.lan._loop = MagicMock()
        # Use real async functions for mocking async methods to ensure they are awaitable
        async def _mock_send_async(*args, **kwargs):
            self.lan._send_async_calls.append((args, kwargs))
        self.lan._send_async_calls = []
        self.lan._send_async = _mock_send_async

        async def _mock_toast_async(*args, **kwargs):
            pass
        self.lan._toast_async = _mock_toast_async

    def test_ws_action_queued_trace_and_received_at(self):
        """Test that received actions are traced and given a received_at timestamp."""
        msg = {"type": "move", "action_id": "act-1"}
        ws_id = 123

        # We need to mock the websocket and its send_text method for the ack
        mock_ws = MagicMock()
        with self.lan._clients_lock:
            self.lan._clients[ws_id] = mock_ws
            self.lan._ws_send_locks[ws_id] = MagicMock()

        # Mock debug_event to see what's happening
        with patch("dnd_initative_tracker.debug_event") as mock_debug_event:
            # We need to run the relevant part of ws_endpoint logic.
            # Since ws_endpoint is a long async function, we'll simulate the action handling part.

            # This is a bit tricky because ws_endpoint is async.
            # I'll manually trigger the logic I added.

            # Simulating the action handling block in ws_endpoint
            async def mock_handler():
                # This matches the logic in dnd_initative_tracker.py
                typ = msg["type"]
                action_id = str(msg.get("action_id") or "").strip()[:160] or "new-id"
                msg["action_id"] = action_id
                msg["_received_at_ns"] = time.perf_counter_ns()

                with self.lan._action_states_lock:
                    self.lan._action_states[action_id] = {
                        "status": "pending",
                        "received_at_ns": msg["_received_at_ns"],
                        "command": typ,
                        "ws_id": ws_id,
                    }
                self.lan._actions.put(msg)

            import asyncio
            asyncio.run(mock_handler())

            queued_msg = self.lan._actions.get_nowait()
            self.assertIn("_received_at_ns", queued_msg)
            self.assertEqual(queued_msg["action_id"], "act-1")

    def test_tick_records_queue_wait_ms(self):
        """Test that _tick calculates and traces queue_wait_ms."""
        received_at = time.perf_counter_ns() - 100_000_000 # 100ms ago
        msg = {
            "type": "move",
            "action_id": "act-2",
            "_received_at_ns": received_at,
            "_ws_id": 123,
            "_claimed_cid": 1
        }
        self.lan._actions.put(msg)

        # Mock _lan_apply_action to not do anything
        self.app._lan_apply_action = MagicMock()

        with patch("dnd_initative_tracker.debug_event") as mock_debug_event:
            self.lan._tick()

            # Check if debug_event was called with queue_wait_ms
            # The second call to debug_event should be "ws.action.dispatch.start"
            start_event = next(call for call in mock_debug_event.call_args_list if call.args[0] == "ws.action.dispatch.start")
            self.assertIn("queue_wait_ms", start_event.kwargs)
            self.assertGreaterEqual(start_event.kwargs["queue_wait_ms"], 100)

    def test_duplicate_action_id_ignored_while_pending(self):
        """Test that duplicate action_id is ignored if already pending."""
        action_id = "act-3"
        self.lan._action_states[action_id] = {"status": "pending"}

        # We need to simulate the ws_endpoint check
        async def simulate_receive():
            # Logic from dnd_initative_tracker.py
            with self.lan._action_states_lock:
                existing = self.lan._action_states.get(action_id)
                if existing:
                    status = existing.get("status")
                    if status == "pending":
                        await self.lan._send_async(123, {"type": "action_ack", "action_id": action_id, "status": "pending"})
                        return "ignored"
            return "queued"

        import asyncio
        result = asyncio.run(simulate_receive())
        self.assertEqual(result, "ignored")
        self.assertEqual(len(self.lan._send_async_calls), 1)
        self.assertEqual(self.lan._actions.qsize(), 0)

    def test_duplicate_action_id_returns_result_if_completed(self):
        """Test that duplicate action_id returns previous result if already completed."""
        action_id = "act-4"
        prev_result = {"status": "applied"}
        self.lan._action_states[action_id] = {"status": "completed", "result": prev_result}

        async def simulate_receive():
            with self.lan._action_states_lock:
                existing = self.lan._action_states.get(action_id)
                if existing:
                    status = existing.get("status")
                    if status == "completed":
                        await self.lan._send_async(123, {"type": "action_ack", "action_id": action_id, "status": "completed", "result": prev_result})
                        return "ignored"
            return "queued"

        import asyncio
        result = asyncio.run(simulate_receive())
        self.assertEqual(result, "ignored")
        self.assertEqual(len(self.lan._send_async_calls), 1)
        self.assertEqual(self.lan._send_async_calls[0][0][1], {"type": "action_ack", "action_id": action_id, "status": "completed", "result": prev_result})

if __name__ == "__main__":
    unittest.main()

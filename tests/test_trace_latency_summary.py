import json
import tempfile
import unittest
from pathlib import Path

from scripts.trace_latency_summary import summarize


class TraceLatencySummaryTests(unittest.TestCase):
    def test_trace_latency_summary_reports_static_plus_dynamic_and_queue_waits(self):
        records = [
            {"event": "span.end", "span": "_dm_tactical_snapshot", "duration_ms": 12.5},
            {"event": "span.end", "span": "lan.snapshot.build", "duration_ms": 20.0, "command": "move"},
            {"event": "lan.state.broadcast_completed", "broadcast_kind": "static_plus_dynamic", "command": "move"},
            {"event": "ws.action.dispatch.start", "command": "attack_request", "queue_wait_ms": 6000},
            {"event": "span.end", "path": "/api/dm/combat", "duration_ms": 700},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
            output = summarize([path])

        self.assertIn("static_plus_dynamic builds: 1", output)
        self.assertIn("_dm_tactical_snapshot calls: 1", output)
        self.assertIn("queue_wait_ms >5000 by command", output)
        self.assertIn("ordinary actions triggering static_plus_dynamic: {'move': 1}", output)


if __name__ == "__main__":
    unittest.main()

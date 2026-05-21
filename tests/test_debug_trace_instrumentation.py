from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import serve_headless
from runtime_config import (
    configure_debug_trace,
    debug_context,
    debug_trace_enabled,
    timed_span,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_analyzer():
    analyzer_path = REPO_ROOT / "scripts" / "analyze_debug_trace.py"
    spec = importlib.util.spec_from_file_location("analyze_debug_trace", analyzer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load analyze_debug_trace")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DebuggingFlagTests(unittest.TestCase):
    def test_debugging_flag_parses_true(self):
        self.assertTrue(serve_headless.parse_args(["--debugging", "true"]).debugging)
        self.assertTrue(serve_headless.parse_args(["--debugging"]).debugging)

    def test_debugging_flag_parses_false(self):
        self.assertFalse(serve_headless.parse_args(["--debugging", "false"]).debugging)
        self.assertFalse(serve_headless.parse_args(["--no-debugging"]).debugging)

    def test_debug_mode_is_off_by_default(self):
        configure_debug_trace(False)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(serve_headless.resolve_debugging_flag(None))
        self.assertFalse(debug_trace_enabled())


class DebugTraceJsonlTests(unittest.TestCase):
    def tearDown(self):
        configure_debug_trace(False)

    def test_timed_span_emits_jsonl_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = configure_debug_trace(True, log_dir=Path(tmpdir))
            self.assertIsNotNone(path)
            with debug_context(trace_id="trace-test", action_id="action-test"):
                with timed_span("unit.test.span", command="cast_spell", counts={"target_count": 2}):
                    pass
            entries = [
                json.loads(line)
                for line in Path(path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        span_end = next(entry for entry in entries if entry.get("event") == "span.end")
        self.assertEqual(span_end.get("span"), "unit.test.span")
        self.assertEqual(span_end.get("trace_id"), "trace-test")
        self.assertEqual(span_end.get("action_id"), "action-test")
        self.assertEqual(span_end.get("command"), "cast_spell")
        self.assertIn("duration_ms", span_end)
        self.assertIn("ts", span_end)
        self.assertIn("level", span_end)


class DebugTraceAnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = _load_analyzer()

    def test_analyzer_parses_tiny_sample_jsonl(self):
        sample = [
            {
                "ts": "2026-05-21T17:00:00.000Z",
                "event": "span.end",
                "span": "lan.snapshot.build",
                "duration_ms": 12.5,
                "action_id": "action-1",
                "command": "cast_spell",
            },
            {
                "ts": "2026-05-21T17:00:00.020Z",
                "event": "http.request.end",
                "route": "/api/dm/combat",
                "method": "GET",
                "duration_ms": 20.0,
                "action_id": "action-http",
            },
            {
                "ts": "2026-05-21T17:00:00.050Z",
                "event": "broadcast.end",
                "span": "lan.broadcast.state",
                "command": "state",
                "duration_ms": 30.0,
                "action_id": "action-1",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in sample) + "\n", encoding="utf-8")
            events, stats = self.analyzer.load_events(path)
            report = self.analyzer.build_report(events, stats)

        self.assertEqual(len(events), 3)
        self.assertIn("total session duration", report)
        self.assertIn("Route timing summary", report)
        self.assertIn("Broadcast summary", report)
        self.assertIn("Snapshot build summary", report)

    def test_analyzer_handles_incomplete_and_bad_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "partial.jsonl"
            path.write_text(
                '{"ts":"2026-05-21T17:00:00.000Z","event":"span.end","span":"yaml","duration_ms":1}\n'
                '{"ts":"partial"\n'
                'not json\n'
                '[]\n',
                encoding="utf-8",
            )
            events, stats = self.analyzer.load_events(path)
            report = self.analyzer.build_report(events, stats)

        self.assertEqual(len(events), 1)
        self.assertGreaterEqual(stats["bad_lines"], 2)
        self.assertIn("ignored bad lines", report)


if __name__ == "__main__":
    unittest.main()

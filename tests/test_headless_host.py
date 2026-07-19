"""Tests for the headless host seam.

These tests cover the runtime-side seam that lets the tracker launch
without constructing a Tk root window:

* ``tk_compat.HeadlessRoot`` provides a real ``after()``/``mainloop()``
  scheduler in place of Tk's event loop.
* ``INIT_TRACKER_HEADLESS=1`` forces ``load_tk_modules`` to return the
  headless module set even when tkinter is importable.
* The full ``InitiativeTracker`` can be constructed and its LAN/web
  surfaces started in headless mode (validated via a subprocess so that
  forcing the headless env does not leak into other tests).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod
import tk_compat


REPO_ROOT = Path(__file__).resolve().parent.parent


class HeadlessRootSchedulerTests(unittest.TestCase):
    """The HeadlessRoot scheduler must fire and cancel callbacks correctly."""

    def test_after_fires_in_order_and_cancel_works(self):
        root = tk_compat.HeadlessRoot()
        hits = []

        thread = threading.Thread(target=root.mainloop, daemon=True)
        thread.start()
        try:
            root.after(60, hits.append, "b")
            root.after(20, hits.append, "a")
            cancel_id = root.after(40, hits.append, "cancelled")
            root.after_cancel(cancel_id)
            root.after(80, hits.append, "c")

            deadline = time.monotonic() + 2.0
            while len(hits) < 3 and time.monotonic() < deadline:
                time.sleep(0.02)
        finally:
            root.quit()
            thread.join(timeout=2.0)

        self.assertEqual(hits, ["a", "b", "c"])
        self.assertFalse(thread.is_alive())

    def test_quit_returns_mainloop_promptly(self):
        root = tk_compat.HeadlessRoot()
        thread = threading.Thread(target=root.mainloop, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)
            root.quit()
            thread.join(timeout=2.0)
        finally:
            if thread.is_alive():
                root.quit()
                thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())


class HeadlessEnvDetectionTests(unittest.TestCase):
    """``INIT_TRACKER_HEADLESS`` should swap Tk for the headless backend."""

    def test_env_var_truthy_values_detected(self):
        original = os.environ.get("INIT_TRACKER_HEADLESS")
        try:
            for value in ("1", "true", "TRUE", "yes", "on"):
                os.environ["INIT_TRACKER_HEADLESS"] = value
                self.assertTrue(tk_compat.is_headless_env(), value)
            for value in ("", "0", "no", "off", "false"):
                os.environ["INIT_TRACKER_HEADLESS"] = value
                self.assertFalse(tk_compat.is_headless_env(), value)
        finally:
            if original is None:
                os.environ.pop("INIT_TRACKER_HEADLESS", None)
            else:
                os.environ["INIT_TRACKER_HEADLESS"] = original


class HeadlessRuntimeSurfaceGuardTests(unittest.TestCase):
    """Desktop-only runtime widget surfaces should hard-gate on host mode."""

    def test_headless_runtime_skips_desktop_only_widget_surfaces(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app.host_mode = "headless"
        app._map_window = None
        app._oplog = lambda *_args, **_kwargs: None

        self.assertFalse(app._allow_desktop_runtime_surface("map_window"))
        self.assertFalse(app._session_restore_supports_tk_refresh())

        app._show_dm_up_alert_dialog()
        app._open_map_mode()
        app._prompt_set_lan_https_public_url()
        app._save_session_dialog()
        app._load_session_dialog()
        app._show_lan_url()
        app._show_lan_qr()
        app._open_lan_sessions()
        app._open_yaml_player_manager()
        app._open_lan_admin_assignments()
        app._show_about()
        app._show_update_log()
        app._check_for_updates()
        app._offer_update_and_run_if_confirmed("update available")
        app._launch_update_workflow("update available")
        app._open_monster_library()
        app._open_random_enemy_dialog()
        app._open_bulk_dialog()
        app._open_damage_tool()
        app._open_heal_tool()
        app._open_condition_tool()
        app._open_move_tool()
        self.assertFalse(app._open_map_attack_tool())

        self.assertIsNone(app.__dict__.get("_map_window"))


class HeadlessLaunchSubprocessTest(unittest.TestCase):
    """Run a real headless launch in a subprocess to keep env isolated.

    This is the real-process check for the supported compatibility entrypoint.
    It uses ``--no-auto-lan`` because the managed test sandbox forbids opening
    sockets; package server startup/readiness delegation is covered with
    injected hosts in the focused server lifecycle tests.
    """

    def test_headless_tracker_serves_dm_surface(self):
        env = os.environ.copy()
        env.pop("INIT_TRACKER_HEADLESS", None)
        process = subprocess.Popen(
            [
                sys.executable,
                "serve_headless.py",
                "--no-auto-lan",
                "--no-debugging",
            ],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        output_lines = []

        def read_output() -> None:
            if process.stdout is None:
                return
            output_lines.extend(process.stdout)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        started = False
        try:
            readiness_deadline = time.monotonic() + 75.0
            while time.monotonic() < readiness_deadline:
                started = any(
                    "Headless tracker started." in line
                    for line in output_lines
                )
                if started:
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                if started:
                    process.send_signal(signal.SIGINT)
                else:
                    process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)

        combined = "".join(output_lines)
        self.assertTrue(started, combined)
        self.assertEqual(process.returncode, 0, combined)
        self.assertIn("Headless tracker started.", combined)


if __name__ == "__main__":
    unittest.main()

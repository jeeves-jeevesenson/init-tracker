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

    This is the integration check for the host seam: in a fresh
    interpreter we set ``INIT_TRACKER_HEADLESS=1``, build the full
    ``InitiativeTracker``, start the LAN server, hit ``/dm`` over HTTP,
    and then shut down cleanly.
    """

    def test_headless_tracker_serves_dm_surface(self):
        script = (
            "import os, sys, threading, time, urllib.request\n"
            "os.environ['INIT_TRACKER_HEADLESS'] = '1'\n"
            "import tk_compat\n"
            "import dnd_initative_tracker as tracker_mod\n"
            "tracker_mod.POC_AUTO_START_LAN = False\n"
            "assert tk_compat.is_headless_env(), 'env not detected'\n"
            "import tkinter as tk\n"
            "assert tk.Tk is tk_compat.HeadlessRoot, 'Tk not swapped for HeadlessRoot'\n"
            "app = tracker_mod.InitiativeTracker()\n"
            "assert isinstance(app, tk_compat.HeadlessRoot)\n"
            "assert hasattr(app, '_lan'), 'LAN controller missing'\n"
            "assert app.host_mode == 'headless', repr(app.host_mode)\n"
            # __getattr__ on dummy widgets makes hasattr() lie, so assert via __dict__.
            "for name in ('tree', 'log_text', '_lan_url_mode_var', '_monster_combo'):\n"
            "    assert name not in app.__dict__, ('Tk widget leaked into headless app: ' + name)\n"
            # Runtime mutations that normally touch UI must not crash in headless mode.
            "assert app._allow_desktop_runtime_surface('map_window') is False\n"
            "assert app._session_restore_supports_tk_refresh() is False\n"
            "app._log('headless smoke test line')\n"
            "app._rebuild_table()\n"
            "app._update_turn_ui()\n"
            "app._show_dm_up_alert_dialog()\n"
            "app._open_map_mode()\n"
            "assert app.__dict__.get('_map_window') is None, 'headless map window should stay unopened'\n"
            "app._prompt_set_lan_https_public_url()\n"
            "app._save_session_dialog()\n"
            "app._load_session_dialog()\n"
            "app._show_lan_url()\n"
            "app._show_lan_qr()\n"
            "app._open_lan_sessions()\n"
            "app._open_yaml_player_manager()\n"
            "app._open_lan_admin_assignments()\n"
            "app._show_about()\n"
            "app._show_update_log()\n"
            "app._check_for_updates()\n"
            "app._offer_update_and_run_if_confirmed('update available')\n"
            "app._launch_update_workflow('update available')\n"
            "app._open_monster_library()\n"
            "app._open_random_enemy_dialog()\n"
            "app._open_bulk_dialog()\n"
            "app._open_damage_tool()\n"
            "app._open_heal_tool()\n"
            "app._open_condition_tool()\n"
            "app._open_move_tool()\n"
            "assert app._open_map_attack_tool() is False\n"
            "th = threading.Thread(target=app.mainloop, daemon=True)\n"
            "th.start()\n"
            "app._lan.cfg.host = '127.0.0.1'\n"
            "app._lan.cfg.port = 18801\n"
            "app._lan.start(quiet=True)\n"
            "status = None\n"
            "for _ in range(40):\n"
            "    try:\n"
            "        with urllib.request.urlopen('http://127.0.0.1:18801/dm', timeout=0.5) as r:\n"
            "            status = r.status\n"
            "            break\n"
            "    except Exception:\n"
            "        time.sleep(0.25)\n"
            "print('STATUS', status)\n"
            "app._lan.stop()\n"
            "app.quit()\n"
            "th.join(timeout=5)\n"
            "print('ALIVE', th.is_alive())\n"
        )

        env = os.environ.copy()
        env.pop("INIT_TRACKER_HEADLESS", None)

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
        combined = result.stdout + "\n" + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("STATUS 200", combined)
        self.assertIn("ALIVE False", combined)


if __name__ == "__main__":
    unittest.main()

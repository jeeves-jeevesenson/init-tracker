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

#!/usr/bin/env python3
"""Headless / server launch entrypoint for the DnD Initiative Tracker.

This entrypoint runs the same backend authority and DM/LAN web surfaces
the desktop app uses, but without constructing a Tkinter root window or
requiring Tk's event loop to keep the process alive.

Usage:
    python3 serve_headless.py [--host HOST] [--port PORT] [--no-auto-lan]

The DM operator surface is reachable at http://HOST:PORT/dm and the
player LAN surface at http://HOST:PORT/.

The headless seam works by setting ``INIT_TRACKER_HEADLESS=1`` before
importing the tracker. ``tk_compat.load_tk_modules`` then returns the
dummy widget set with ``tk.Tk`` swapped for ``HeadlessRoot``, which
implements the ``after()``/``mainloop()`` semantics the runtime relies
on without opening any real window.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from typing import Optional, Sequence


def _force_headless_env() -> None:
    os.environ["INIT_TRACKER_HEADLESS"] = "1"


def _override_lan_cfg(app, host: Optional[str], port: Optional[int]) -> None:
    lan = getattr(app, "_lan", None)
    if lan is None:
        return
    cfg = getattr(lan, "cfg", None)
    if cfg is None:
        return
    if host is not None:
        cfg.host = str(host)
    if port is not None:
        cfg.port = int(port)


def _shutdown(app) -> None:
    try:
        lan = getattr(app, "_lan", None)
        if lan is not None:
            lan._polling = False
            lan.stop()
    except Exception:
        pass
    try:
        app.quit()
    except Exception:
        pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the DnD Initiative Tracker as a headless backend + DM web host.",
    )
    parser.add_argument("--host", default=None, help="Override LAN bind host (default 0.0.0.0).")
    parser.add_argument("--port", type=int, default=None, help="Override LAN bind port (default 8787).")
    parser.add_argument(
        "--no-auto-lan",
        action="store_true",
        help="Do not auto-start the LAN server (start it via the DM admin surface instead).",
    )
    args = parser.parse_args(argv)

    _force_headless_env()

    # Import tracker AFTER setting INIT_TRACKER_HEADLESS so tk_compat returns
    # the dummy/headless modules and InitiativeTracker inherits HeadlessRoot.
    import dnd_initative_tracker as tracker_mod

    if args.no_auto_lan:
        tracker_mod.POC_AUTO_START_LAN = False

    app = tracker_mod.InitiativeTracker()
    _override_lan_cfg(app, args.host, args.port)

    def _handle_signal(_signum, _frame):
        _shutdown(app)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except Exception:
            pass

    try:
        url = app._lan._best_lan_url()
    except Exception:
        url = ""
    sys.stdout.write("Headless tracker started.\n")
    if url:
        sys.stdout.write(f"  DM operator surface: {url}dm\n")
        sys.stdout.write(f"  Player LAN surface:  {url}\n")
    sys.stdout.write("Press Ctrl+C to stop.\n")
    sys.stdout.flush()

    try:
        app.mainloop()
    except KeyboardInterrupt:
        _shutdown(app)
    return 0


if __name__ == "__main__":
    sys.exit(main())

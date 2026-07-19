#!/usr/bin/env python3
"""Headless / server launch entrypoint for the DnD Initiative Tracker.

This entrypoint runs the same backend authority and DM/LAN web surfaces
the desktop app uses, but without constructing a Tkinter root window or
requiring Tk's event loop to keep the process alive.

Usage:
    python3 serve_headless.py [--host HOST] [--port PORT] [--no-auto-lan]
        [--debugging [true|false] | --no-debugging]

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

from init_tracker_server.runtime_host import HeadlessRuntimeHost

from runtime_config import (
    config as runtime_cfg,
    configure_debug_trace,
    debug_trace_path,
    debugging_env_enabled,
    parse_bool_value,
)


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


def _parse_debugging_value(raw: str) -> bool:
    parsed = parse_bool_value(raw, default=None)
    if parsed is None:
        raise argparse.ArgumentTypeError("expected true or false")
    return bool(parsed)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the DnD Initiative Tracker as a headless backend + DM web host.",
    )
    parser.add_argument("--host", default=None, help=f"Override LAN bind host (default {runtime_cfg.host}).")
    parser.add_argument("--port", type=int, default=None, help=f"Override LAN bind port (default {runtime_cfg.port}).")
    parser.add_argument(
        "--no-auto-lan",
        action="store_true",
        help="Do not auto-start the LAN server (start it via the DM admin surface instead).",
    )
    parser.add_argument(
        "--debugging",
        nargs="?",
        const=True,
        default=None,
        type=_parse_debugging_value,
        help="Write opt-in live debug JSONL trace logs. Bare --debugging means true.",
    )
    parser.add_argument(
        "--no-debugging",
        dest="debugging",
        action="store_false",
        help="Disable live debug trace logging even if INIT_TRACKER_DEBUGGING is set.",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


def resolve_debugging_flag(cli_value: Optional[bool]) -> bool:
    if cli_value is None:
        return debugging_env_enabled()
    return bool(cli_value)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    _force_headless_env()
    debugging_enabled = resolve_debugging_flag(args.debugging)
    os.environ["INIT_TRACKER_DEBUGGING"] = "1" if debugging_enabled else "0"
    configure_debug_trace(debugging_enabled)

    # If we are in production mode, ensure directories exist
    runtime_cfg.ensure_dirs()

    # Import tracker AFTER setting INIT_TRACKER_HEADLESS so tk_compat returns
    # the dummy/headless modules and InitiativeTracker inherits HeadlessRoot.
    import dnd_initative_tracker as tracker_mod

    auto_start_lan = not args.no_auto_lan
    tracker_mod.POC_AUTO_START_LAN = auto_start_lan

    runtime_host = HeadlessRuntimeHost(
        lambda: tracker_mod.InitiativeTracker(auto_start_lan=False),
        prepare_runtime=lambda current_app: _override_lan_cfg(
            current_app,
            args.host,
            args.port,
        ),
        auto_start_server=auto_start_lan,
    )
    app = runtime_host.start()

    def _handle_signal(_signum, _frame):
        runtime_host.stop()

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
    if debugging_enabled and debug_trace_path() is not None:
        sys.stdout.write(f"  Debug trace: {debug_trace_path()}\n")
    if url:
        sys.stdout.write(f"  DM operator surface: {url}dm\n")
        sys.stdout.write(f"  Player LAN surface:  {url}\n")
    sys.stdout.write("Press Ctrl+C to stop.\n")
    sys.stdout.flush()

    try:
        runtime_host.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

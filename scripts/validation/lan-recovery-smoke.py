#!/usr/bin/env python3
"""LAN reconnect-recovery browser smoke.

Boots the headless tracker on a free port, opens the LAN page in a
real Chromium via Playwright with ``?ws_debug=1`` so that
``logWsDebug`` emits ``ws_debug:*`` client-log entries, then sits
idle for 30 seconds and asserts that:

  * the page initialises exactly once (no service-worker reload loop),
  * one WebSocket survives baseline recovery (no escalation closes
    a healthy socket),
  * no ``beforeunload`` / ``pagehide`` fires during idle recovery,
  * ``recovery_escalation_action`` (if any) requested missing
    baseline data instead of soft-reconnecting.

Run manually:

    ./.venv/bin/python scripts/validation/lan-recovery-smoke.py

Exits non-zero on any assertion failure.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IDLE_SECONDS = 30
SERVER_BOOT_TIMEOUT = 30.0


def _find_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_http(url: str, timeout: float) -> None:
    import urllib.request

    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return
        except Exception as err:
            last_err = err
        time.sleep(0.25)
    raise RuntimeError(f"server at {url} never became ready: {last_err!r}")


INIT_SCRIPT = r"""
(() => {
  const debugEvents = [];
  const pageDebugEvents = [];
  const lifecycleEvents = [];
  const wsRecords = [];
  window.__SMOKE = { debugEvents, pageDebugEvents, lifecycleEvents, wsRecords };

  const origFetch = window.fetch.bind(window);
  window.fetch = function(input, init) {
    try {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      if (url && url.indexOf("/api/client-log") !== -1 && init && typeof init.body === "string"){
        try {
          const payload = JSON.parse(init.body);
          if (payload && typeof payload.message === "string"){
            if (payload.message.indexOf("ws_debug:") === 0){
              debugEvents.push({
                event: payload.message.slice("ws_debug:".length),
                stack: payload.stack || "",
                ts: payload.timestamp || "",
              });
            } else if (payload.message.indexOf("page_debug:") === 0){
              pageDebugEvents.push({
                event: payload.message.slice("page_debug:".length),
                stack: payload.stack || "",
                ts: payload.timestamp || "",
              });
            }
          }
        } catch (_) {}
        // Resolve the smoke-only side-channel without bothering the server.
        return Promise.resolve(new Response("{\"logged\":true}", {
          status: 200,
          headers: {"Content-Type": "application/json"},
        }));
      }
    } catch (_) {}
    return origFetch(input, init);
  };
  if (navigator.sendBeacon){
    const origBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = function(url, data){
      try {
        if (url && url.indexOf("/api/client-log") !== -1){
          let text = "";
          if (typeof data === "string") text = data;
          else if (data instanceof Blob) {
            // best-effort: skip; beacons are rare in the smoke window
          }
          if (text){
            try {
              const payload = JSON.parse(text);
              if (payload && typeof payload.message === "string"
                  && payload.message.indexOf("ws_debug:") === 0){
                debugEvents.push({
                  event: payload.message.slice("ws_debug:".length),
                  stack: payload.stack || "",
                  ts: payload.timestamp || "",
                });
              }
            } catch (_) {}
            return true;
          }
        }
      } catch (_) {}
      return origBeacon(url, data);
    };
  }

  const NativeWS = window.WebSocket;
  function TrackedWS(url, protocols){
    const sock = protocols === undefined
      ? new NativeWS(url)
      : new NativeWS(url, protocols);
    const idx = wsRecords.length;
    const record = {
      idx,
      url: String(url),
      openedAt: Date.now(),
      closedAt: null,
      closeCode: null,
      closeReason: null,
    };
    wsRecords.push(record);
    sock.addEventListener("close", (ev) => {
      record.closedAt = Date.now();
      record.closeCode = ev.code;
      record.closeReason = ev.reason || "";
    });
    return sock;
  }
  TrackedWS.prototype = NativeWS.prototype;
  TrackedWS.CONNECTING = NativeWS.CONNECTING;
  TrackedWS.OPEN = NativeWS.OPEN;
  TrackedWS.CLOSING = NativeWS.CLOSING;
  TrackedWS.CLOSED = NativeWS.CLOSED;
  window.WebSocket = TrackedWS;

  for (const name of ["beforeunload", "pagehide", "unload", "visibilitychange"]) {
    window.addEventListener(name, () => {
      lifecycleEvents.push({event: name, at: Date.now(), visibility: document.visibilityState});
    }, {capture: true});
  }
})();
"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as err:
        print(f"playwright not available: {err}", file=sys.stderr)
        return 2

    port = _find_open_port()
    base_url = f"http://127.0.0.1:{port}"
    env = dict(os.environ)
    env["INIT_TRACKER_HEADLESS"] = "1"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "serve_headless.py"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    print(f"[smoke] starting headless tracker on {base_url}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_http(base_url + "/", SERVER_BOOT_TIMEOUT)
    except Exception:
        proc.terminate()
        out = ""
        try:
            out = proc.stdout.read() if proc.stdout else ""
        except Exception:
            pass
        print(out, file=sys.stderr)
        raise

    failures: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                context = browser.new_context()
                context.add_init_script(INIT_SCRIPT)
                page = context.new_page()
                console_logs: list[str] = []
                page.on("console", lambda msg: console_logs.append(f"{msg.type}: {msg.text}"))
                page.on("pageerror", lambda err: console_logs.append(f"pageerror: {err}"))

                page.goto(
                    f"{base_url}/?ws_debug=1&v=recovery-escalation-smoke",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                # Wait for the LAN boot marker to ensure the page wired up.
                page.wait_for_function(
                    "document.documentElement.dataset.lanBoot === 'true'",
                    timeout=15000,
                )

                print(f"[smoke] page booted; sitting idle for {IDLE_SECONDS}s")
                time.sleep(IDLE_SECONDS)

                snapshot = page.evaluate(
                    """() => ({
                      debugEvents: window.__SMOKE.debugEvents.slice(),
                      pageDebugEvents: window.__SMOKE.pageDebugEvents.slice(),
                      lifecycleEvents: window.__SMOKE.lifecycleEvents.slice(),
                      wsRecords: window.__SMOKE.wsRecords.map((r) => ({...r})),
                      lanBoot: document.documentElement.dataset.lanBoot || "",
                      readyState: document.readyState,
                    })"""
                )
            finally:
                browser.close()

        debug_events = snapshot.get("debugEvents", [])
        page_debug_events = snapshot.get("pageDebugEvents", [])
        lifecycle = snapshot.get("lifecycleEvents", [])
        ws_records = snapshot.get("wsRecords", [])
        event_counts: dict[str, int] = {}
        for entry in debug_events:
            event_counts[entry["event"]] = event_counts.get(entry["event"], 0) + 1
        page_event_counts: dict[str, int] = {}
        for entry in page_debug_events:
            page_event_counts[entry["event"]] = page_event_counts.get(entry["event"], 0) + 1

        open_sockets = [r for r in ws_records if r["closedAt"] is None]
        closed_sockets = [r for r in ws_records if r["closedAt"] is not None]
        idle_lifecycle = [
            ev
            for ev in lifecycle
            if ev["event"] in ("beforeunload", "pagehide", "unload")
        ]
        page_init_count = page_event_counts.get("lan_page_init", 0)
        duplicate_bootstrap_count = page_event_counts.get("duplicate_bootstrap", 0)
        escalation_actions = [
            entry
            for entry in debug_events
            if entry["event"] == "recovery_escalation_action"
        ]
        bad_escalations = []
        for entry in escalation_actions:
            try:
                stack = json.loads(entry["stack"]) if entry.get("stack") else {}
            except Exception:
                stack = {}
            action = stack.get("action")
            if action != "request_missing_baseline":
                bad_escalations.append({"action": action, "stack": stack})

        print(f"[smoke] websocket records: {len(ws_records)} (open={len(open_sockets)}, closed={len(closed_sockets)})")
        print(f"[smoke] ws_debug event counts: {event_counts}")
        print(f"[smoke] page_debug event counts: {page_event_counts}")
        print(f"[smoke] idle lifecycle events: {idle_lifecycle}")
        if closed_sockets:
            for r in closed_sockets:
                print(f"[smoke]   closed ws idx={r['idx']} code={r['closeCode']} reason={r['closeReason']!r}")

        if len(ws_records) == 0:
            failures.append("no websocket was opened by the page")
        if len(open_sockets) != 1:
            failures.append(f"expected exactly one open websocket after idle, got {len(open_sockets)}")
        if len(ws_records) > 1:
            failures.append(f"page opened {len(ws_records)} websockets during idle (expected 1)")
        if page_init_count != 1:
            failures.append(f"lan_page_init fired {page_init_count} times (expected exactly 1)")
        if duplicate_bootstrap_count:
            failures.append(f"duplicate_bootstrap fired {duplicate_bootstrap_count} times (expected 0)")
        if idle_lifecycle:
            failures.append(f"unexpected lifecycle events during idle: {idle_lifecycle}")
        if bad_escalations:
            failures.append(f"recovery escalation took non-baseline action: {bad_escalations}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    if failures:
        print("[smoke] FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("[smoke] PASS: reconnect recovery hotfix held under 30s idle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

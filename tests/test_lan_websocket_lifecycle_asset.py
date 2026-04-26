import os
import subprocess
import textwrap
import unittest
from pathlib import Path
from shutil import which


REPO_ROOT = Path(__file__).resolve().parent.parent
LAN_INDEX = REPO_ROOT / "assets" / "web" / "lan" / "index.html"


def _extract_function(source: str, name: str) -> str:
    start = source.index(f"  function {name}(")
    brace = source.index("{", start)
    depth = 0
    for idx in range(brace, len(source)):
        char = source[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    raise AssertionError(f"Could not extract function {name}")


@unittest.skipUnless(which("node"), "node not installed")
class LanWebsocketLifecycleAssetTests(unittest.TestCase):
    def test_lan_websocket_lifecycle_keeps_single_active_socket(self):
        html = LAN_INDEX.read_text(encoding="utf-8")
        helper_start = html.index("  function isSocketConnectingOrOpen")
        helper_end = html.index("  function resize()", helper_start)
        lifecycle_helpers = html[helper_start:helper_end]
        connect_fn = _extract_function(html, "connect")

        script = textwrap.dedent(
            f"""
            const assert = require("assert");
            const sent = [];
            const connStates = [];
            const waitingUpdates = [];
            const wsDebugEvents = [];
            let nextTimerId = 1;
            const timers = new Map();
            global.setTimeout = (fn, delay) => {{
              const id = nextTimerId++;
              timers.set(id, {{fn, delay}});
              return id;
            }};
            global.clearTimeout = (id) => {{
              timers.delete(id);
            }};
            function fireTimer(id) {{
              const timer = timers.get(id);
              assert(timer, `missing timer ${{id}}`);
              timers.delete(id);
              timer.fn();
            }}
            class FakeWebSocket {{
              static CONNECTING = 0;
              static OPEN = 1;
              static CLOSING = 2;
              static CLOSED = 3;
              static instances = [];
              constructor(url) {{
                this.url = url;
                this.readyState = FakeWebSocket.CONNECTING;
                this.listeners = {{}};
                this.closed = [];
                FakeWebSocket.instances.push(this);
              }}
              addEventListener(type, fn) {{
                this.listeners[type] = fn;
              }}
              send(payload) {{
                sent.push(JSON.parse(payload));
              }}
              open() {{
                this.readyState = FakeWebSocket.OPEN;
                this.listeners.open?.({{}});
              }}
              message(payload) {{
                this.listeners.message?.({{data: JSON.stringify(payload)}});
              }}
              close(code, reason) {{
                this.closed.push({{code, reason}});
                this.readyState = FakeWebSocket.CLOSED;
                this.listeners.close?.({{code, reason, wasClean: code === 1000}});
              }}
            }}
            global.WebSocket = FakeWebSocket;

            let ws = null;
            let wsGeneration = 0;
            let reconnectTimer = null;
            let reconnecting = false;
            let reconnectRecoveryPending = false;
            let reconnectRecoveryStateSeen = false;
            let reconnectRecoveryClaimSeen = false;
            let reconnectRecoveryGridSeen = false;
            let reconnectFallbackRequested = false;
            let reconnectEscalated = false;
            let reconnectCycle = 0;
            let reconnectFallbackTimer = null;
            let reconnectEscalationTimer = null;
            const reconnectFallbackDelayMs = 1800;
            const reconnectEscalationDelayMs = 2200;
            let claimStateSeen = false;
            let claimDataReady = false;
            let lastPcList = [];
            let wsUrl = "ws://127.0.0.1:8787/ws";
            let battleLogSubscribed = false;
            let isMapView = false;
            let clientId = "client-test";
            let isPlanning = false;
            let planningSnapshotLocked = false;
            const planningFreezeTypes = new Set();
            function setConn(ok, text) {{ connStates.push([ok, text]); }}
            function closeConnPopover() {{}}
            function updateWaitingOverlay() {{ waitingUpdates.push(reconnectRecoveryPending); }}
            function gridReady() {{ return false; }}
            function send(msg) {{
              if (!ws || ws.readyState !== WebSocket.OPEN) return;
              ws.send(JSON.stringify(msg));
            }}
            function refreshMapViewLogPolling() {{}}
            function logWsDebug(eventName, details) {{
              wsDebugEvents.push({{eventName, details}});
            }}

            {lifecycle_helpers}
            {connect_fn}

            connect();
            connect();
            assert.strictEqual(FakeWebSocket.instances.length, 1, "repeated connect() must not create a second CONNECTING socket");
            const first = FakeWebSocket.instances[0];
            first.open();
            connect();
            assert.strictEqual(FakeWebSocket.instances.length, 1, "connect() must not create a second OPEN socket");
            assert.deepStrictEqual(
              sent.map((msg) => msg.type).slice(0, 4),
              ["client_hello", "planning_hello", "grid_request", "terrain_request"],
              "open socket should still send startup requests",
            );

            const reconnectId = setTimeout(() => connect(), 1000);
            reconnectTimer = reconnectId;
            assert(timers.has(reconnectId), "test reconnect timer should be pending before open");
            first.open();
            assert(!timers.has(reconnectId), "successful open must clear pending reconnect timer");

            ws = null;
            connect();
            const second = FakeWebSocket.instances[1];
            const sentBeforeStaleOpen = sent.length;
            first.open();
            assert.strictEqual(sent.length, sentBeforeStaleOpen, "stale onopen must be ignored");
            first.message({{type: "state", state: {{}}, you: {{claimed_cid: null}}}});
            first.close(1006, "stale");
            assert.strictEqual(FakeWebSocket.instances.length, 2, "stale callbacks must not create another socket");

            second.open();
            assert.strictEqual(reconnectTimer, null, "no reconnect timer should be pending while active socket is open");
            second.close(1006, "network");
            const closeDebug = wsDebugEvents.find((entry) => entry.eventName === "onclose" && entry.details.reason === "network");
            assert(closeDebug, "active close should emit websocket debug lifecycle payload");
            assert.strictEqual(closeDebug.details.wsGeneration, 2, "close debug payload must include wsGeneration");
            assert.strictEqual(closeDebug.details.code, 1006, "close debug payload must include close code");
            assert.strictEqual(closeDebug.details.reason, "network", "close debug payload must include close reason");
            assert.strictEqual(closeDebug.details.wasClean, false, "close debug payload must include wasClean");
            assert.strictEqual(closeDebug.details.websocketUrl, wsUrl, "close debug payload must include websocket URL");
            assert.strictEqual(closeDebug.details.intentionalClose, false, "network close should not be marked intentional");
            const activeReconnectTimer = reconnectTimer;
            assert(activeReconnectTimer && timers.has(activeReconnectTimer), "real active close should schedule one reconnect");
            second.close(1006, "duplicate-close");
            assert.strictEqual(reconnectTimer, activeReconnectTimer, "duplicate close callback should not schedule another reconnect");
            fireTimer(activeReconnectTimer);
            assert.strictEqual(FakeWebSocket.instances.length, 3, "scheduled reconnect should create one replacement socket");

            const third = FakeWebSocket.instances[2];
            third.open();
            const socketsBeforeRecovery = FakeWebSocket.instances.length;
            beginReconnectRecoveryCycle();
            const fallbackId = reconnectFallbackTimer;
            fireTimer(fallbackId);
            assert.strictEqual(
              FakeWebSocket.instances.length,
              socketsBeforeRecovery,
              "recovery fallback state/grid/terrain requests must not create sockets",
            );
            const escalationId = reconnectEscalationTimer;
            fireTimer(escalationId);
            assert.strictEqual(
              FakeWebSocket.instances.length,
              socketsBeforeRecovery,
              "recovery escalation soft reconnect must close the active socket before reconnecting",
            );
            assert.strictEqual(third.closed.length, 1, "soft reconnect should close the active socket once");
            const reconnectsAfterEscalation = timers.size;
            scheduleReconnect(200);
            scheduleReconnect(200);
            assert.strictEqual(timers.size, reconnectsAfterEscalation, "only one reconnect timer may be pending");
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

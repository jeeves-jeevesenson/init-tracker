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
            const document = {{ visibilityState: "visible" }};
            const pageInstanceId = "page-1";
            let lastPageLifecycleEvent = "pageshow";
            function setConn(ok, text) {{ connStates.push([ok, text]); }}
            function closeConnPopover() {{}}
            function updateWaitingOverlay() {{ waitingUpdates.push(reconnectRecoveryPending); }}
            let gridIsReady = false;
            function gridReady() {{ return gridIsReady; }}
            function send(msg) {{
              if (!ws || ws.readyState !== WebSocket.OPEN) return;
              ws.send(JSON.stringify(msg));
            }}
            function refreshMapViewLogPolling() {{}}
            function logWsDebug(eventName, details) {{
              wsDebugEvents.push({{
                eventName,
                details: {{
                  pageInstanceId,
                  lastPageLifecycleEvent,
                  pageVisibility: document.visibilityState,
                  ...details,
                }},
              }});
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
            assert.strictEqual(closeDebug.details.pageInstanceId, "page-1", "close debug payload must include page instance id");
            assert.strictEqual(closeDebug.details.lastPageLifecycleEvent, "pageshow", "close debug payload must include page lifecycle context");
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
              "recovery escalation must not create a socket while the active socket is open",
            );
            assert.strictEqual(third.closed.length, 0, "recovery escalation must not close a healthy active socket");
            const escalationDebug = wsDebugEvents.find((entry) => entry.eventName === "recovery_escalation_action");
            assert(escalationDebug, "recovery escalation action must be debug logged");
            assert.strictEqual(
              escalationDebug.details.action,
              "request_missing_baseline",
              "open-socket recovery escalation should request missing baseline data instead of reconnecting",
            );
            reconnectRecoveryStateSeen = true;
            reconnectRecoveryClaimSeen = true;
            reconnectRecoveryGridSeen = true;
            claimStateSeen = true;
            lastPcList = [{{cid: 1, name: "Fred"}}];
            gridIsReady = true;
            updateClaimDataReady();
            maybeFinishReconnectRecovery();
            assert.strictEqual(reconnectRecoveryPending, false, "healthy baseline must finish recovery");
            assert.strictEqual(reconnectFallbackRequested, false, "healthy baseline must clear fallback state");
            assert.strictEqual(reconnectEscalated, false, "healthy baseline must clear escalation state");
            assert.strictEqual(reconnectFallbackTimer, null, "healthy baseline must clear fallback timer");
            assert.strictEqual(reconnectEscalationTimer, null, "healthy baseline must clear escalation timer");
            const recoveryCancelDebug = wsDebugEvents.find(
              (entry) => entry.eventName === "recovery_cancelled"
                && entry.details.reason === "healthy_baseline_received",
            );
            assert(recoveryCancelDebug, "healthy recovery completion must be debug logged");
            const reconnectsAfterEscalation = timers.size;
            scheduleReconnect(200);
            scheduleReconnect(200);
            assert.strictEqual(timers.size, reconnectsAfterEscalation + 1, "only one reconnect timer may be pending");
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

    def test_lan_bootstrap_guard_suppresses_same_shell_navigation(self):
        html = LAN_INDEX.read_text(encoding="utf-8")
        create_page_instance_id = _extract_function(html, "createPageInstanceId")
        claim_lan_bootstrap = _extract_function(html, "claimLanBootstrap")
        is_lan_shell_path = _extract_function(html, "isLanShellPath")
        should_suppress = _extract_function(html, "shouldSuppressDeepLinkNavigation")
        route_deep_link = _extract_function(html, "routeDeepLink")

        script = textwrap.dedent(
            f"""
            const assert = require("assert");
            const logEntries = [];
            const locationState = new URL("http://127.0.0.1:8787/?v=reload-loop");
            const location = {{
              get href() {{ return locationState.href; }},
              set href(value) {{
                throw new Error(`unexpected navigation to ${{value}}`);
              }},
              get origin() {{ return locationState.origin; }},
              get pathname() {{ return locationState.pathname; }},
              get search() {{ return locationState.search; }},
            }};
            const window = {{
              __INITTRACKER_LAN_PAGE_INSTANCE_ID: undefined,
              __INITTRACKER_LAN_BOOTSTRAP_STATE: undefined,
              crypto: {{
                randomUUID() {{ return "page-1"; }},
              }},
            }};
            const normalizedPath = location.pathname.replace(/\\/+$/, "") || "/";
            function logPageDebug(eventName, details) {{
              logEntries.push({{eventName, details}});
            }}

            global.window = window;
            global.location = location;
            {create_page_instance_id}
            {claim_lan_bootstrap}
            {is_lan_shell_path}
            {should_suppress}
            {route_deep_link}

            const pageInstanceId = createPageInstanceId();
            assert.strictEqual(pageInstanceId, "page-1", "page instance id must remain stable within one document");
            assert.strictEqual(claimLanBootstrap(pageInstanceId, logPageDebug), true, "first bootstrap claim must succeed");
            assert.strictEqual(claimLanBootstrap(pageInstanceId, logPageDebug), false, "duplicate bootstrap must be blocked");
            routeDeepLink("/", "service_worker_deep_link");

            assert(logEntries.some((entry) => entry.eventName === "lan_page_init"), "page init must be logged once");
            assert(logEntries.some((entry) => entry.eventName === "duplicate_bootstrap"), "duplicate bootstrap must be logged");
            const suppressed = logEntries.find((entry) => entry.eventName === "navigation_suppressed");
            assert(suppressed, "same-shell deep link must be suppressed instead of reloading the page");
            assert.strictEqual(suppressed.details.currentPath, "/", "suppressed navigation must report current path");
            assert.strictEqual(suppressed.details.targetPath, "/", "suppressed navigation must report target path");
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

    def test_recovery_escalation_does_not_reload_or_rebootstrap_page(self):
        html = LAN_INDEX.read_text(encoding="utf-8")
        begin_recovery = _extract_function(html, "beginReconnectRecoveryCycle")

        self.assertIn('requestReconnectRecoveryBaseline("escalation")', begin_recovery)
        self.assertNotIn("softReconnect(", begin_recovery)
        self.assertNotIn("location.href", begin_recovery)
        self.assertNotIn("location.reload", begin_recovery)
        self.assertNotIn("location.replace", begin_recovery)


if __name__ == "__main__":
    unittest.main()

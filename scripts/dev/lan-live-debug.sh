#!/bin/bash
# scripts/dev/lan-live-debug.sh
# Start a clean live-debug server for init-tracker.

set -euo pipefail

# Ensure we are in the repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "=== init-tracker Live Debug Start ==="
echo "Repo root: $REPO_ROOT"
echo ""

# 1. Environment Check
echo "--- Git Status ---"
git status --short
echo ""

echo "--- Port 8787 Listeners ---"
if command -v lsof >/dev/null 2>&1; then
    lsof -i :8787 || echo "No listeners on port 8787."
elif command -v netstat >/dev/null 2>&1; then
    netstat -tuln | grep :8787 || echo "No listeners on port 8787."
else
    echo "lsof/netstat not found, skipping port check."
fi
echo ""

# 2. Optional Kill
if [[ "${1:-}" == "--kill-existing" ]]; then
    echo "--- Killing Existing Processes ---"
    pkill -f "serve_headless.py" || true
    pkill -f "uvicorn" || true
    sleep 1
fi

# 3. Log Rotation
echo "--- Preparing Logs ---"
mkdir -p logs
for log in logs/websocket_debug.jsonl logs/client_errors.log logs/lan_server.log; do
    if [[ -f "$log" ]]; then
        echo "Rotating $log..."
        mv "$log" "${log}.old" || true
    fi
    touch "$log"
done
echo ""

# 4. Launch
echo "--- Launching Server ---"
echo "URLs for real LAN browser:"
echo "  http://192.168.1.235:8787/"
echo "  http://192.168.1.235:8787/dm"
echo ""

export INIT_TRACKER_HEADLESS=1
export INITTRACKER_WS_DEBUG=1
export LAN_PERF_DEBUG=1

# Use venv if it exists
PYTHON_BIN="./.venv/bin/python3"
if [[ ! -f "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" serve_headless.py --host 0.0.0.0 --port 8787

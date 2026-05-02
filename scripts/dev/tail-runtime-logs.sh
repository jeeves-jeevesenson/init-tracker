#!/bin/bash
# scripts/dev/tail-runtime-logs.sh
# Monitor runtime logs during live browser reproduction.

set -euo pipefail

# Ensure we are in the repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "=== init-tracker Runtime Log Monitor ==="
mkdir -p logs

# Ensure log files exist so tail doesn't complain
touch logs/websocket_debug.jsonl
touch logs/client_errors.log
touch logs/lan_server.log

echo "Tailing logs (Ctrl+C to stop)..."
echo "Files: logs/websocket_debug.jsonl logs/client_errors.log logs/lan_server.log"
echo ""

tail -f logs/websocket_debug.jsonl logs/client_errors.log logs/lan_server.log

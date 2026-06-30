#!/usr/bin/env bash
set -euo pipefail

# scripts/chatgpt_context_refresher.sh
# Generate a compact current-state refresher for a fresh ChatGPT session.

# Change to repo root
cd "$(git rev-parse --show-toplevel)"

OUTPUT_PATH="${1:-/tmp/init-tracker-context-refresher.txt}"

{
    echo "INIT-TRACKER CONTEXT REFRESHER"
    echo "Generated: $(date)"
    echo "Repo path: $(pwd)"
    echo "Current branch: $(git rev-parse --abbrev-ref HEAD)"
    echo "Latest commit: $(git log -1 --oneline --decorate)"
    echo
    echo "--- GIT STATUS ---"
    git status --short
    echo
    echo "--- DIFF STATS ---"
    echo "Dirty diff stat:"
    git diff --stat
    echo
    echo "Staged diff stat:"
    git diff --cached --stat
    echo
    echo "--- RECENT HISTORY (Last 8) ---"
    git log -n 8 --oneline
    echo
    echo "--- CURRENT WORK LEDGER (docs/work_items/current_work.md) ---"
    if [ -f "docs/work_items/current_work.md" ]; then
        head -n 120 "docs/work_items/current_work.md"
    else
        echo "LEDGER MISSING: docs/work_items/current_work.md not found."
    fi
    echo
    echo "--- ACTIVE DURABLE DOCS ---"
    echo "- GEMINI.md"
    echo "- AGENTS.md"
    echo "- CLAUDE.md"
    echo "- majorTODO.md"
    echo "- docs/production_recovery_living_doc_20260526.md"
    echo
    echo "--- CURRENT GATE / ORDER SUMMARY ---"
    echo "A0: Agent Workflow (CURRENT)"
    echo "Gate 1: Map Surface Contract"
    echo "Gate 2: Spell/Capability Contract"
    echo "Gate 3: Combat Responsiveness"
    echo "Gate 4: Resource/Rest/Pact"
    echo "Gate 5: Experimental Quarantine"
    echo "Gate 6: Production Runbook"
    echo
    echo "--- CAVEATS ---"
    echo "Note: docs/runtime_reports/wip_diffs/ may show as untracked."
    echo
    echo "--- LATEST RUNTIME REPORTS (Last 10) ---"
    ls -dt docs/runtime_reports/* 2>/dev/null | head -n 10 | xargs -n 1 basename
    echo
    echo "--- LATEST AGENT_OPS DOCS ---"
    ls -dt docs/agent_ops/* 2>/dev/null | xargs -n 1 basename
    echo
    echo "--- COMMANDS FOR FRESH SESSIONS ---"
    echo "- scripts/agent_context_bundle.sh (Broad bundle)"
    echo "- scripts/chatgpt_context_refresher.sh (Compact refresher)"
    echo "- scripts/agent_gate_validate.sh <gate-id> (Validation)"
    echo
    echo "--- HOW TO USE THIS REFRESHER ---"
    echo "Paste the following as your first message in a fresh ChatGPT session:"
    echo "\"I’m continuing init-tracker. Here is the current context refresher. First summarize current status, dirty state, unknowns, and next safe action. Do not write an implementation task until context is established.\""
    echo
    echo "--- DEVELOPER ROLE ---"
    echo "Product owner, smoke tester, final push/deploy approver."
    echo "Does NOT perform manual code review; agents are responsible for correctness."
    echo
    echo "--- AGENT DEFAULTS ---"
    echo "AGY / Antigravity CLI is the default executor."
    echo "Gemini CLI is retired for this workflow."
    echo "Codex only when the developer explicitly says 'Codex' or asks whether Codex is worth the spend."
    echo
    echo "--- TASK DISCIPLINE ---"
    echo "- One task per message."
    echo "- Every task MUST have a unique task ID (e.g., ITR-YYYYMMDD-AX-YY)."
    echo "- Tie all summaries back to the active task ID."
    echo
    echo "--- WHAT NOT TO ASSUME ---"
    echo "Do NOT guess: FQDNs, hostnames, ports, hardware, production topology, current commit, dirty state, or runtime paths."
} > "$OUTPUT_PATH"

echo "Context refresher generated at: $OUTPUT_PATH"

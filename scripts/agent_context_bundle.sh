#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== init-tracker agent context bundle =="
echo
echo "Latest git commit:"
git log -1 --oneline --decorate

echo
echo "Git status:"
status="$(git status --short)"
if [ -n "$status" ]; then
  printf '%s\n' "$status"
else
  echo "(clean)"
fi

echo
echo "Active recovery doc:"
echo "docs/production_recovery_living_doc_20260526.md"

echo
echo "Gate order:"
echo "A0 agent workflow and instruction control"
echo "Gate 1 map surface contract restoration"
echo "Gate 2 spell/capability contract stabilization"
echo "Gate 3 combat responsiveness and latency"
echo "Gate 4 resource/rest/pact mechanics"
echo "Gate 5 experimental feature quarantine"
echo "Gate 6 production deployment runbook"

echo
echo "Current untracked caveats:"
untracked="$(git status --short | grep '^?? ' || true)"
if [ -n "$untracked" ]; then
  printf '%s\n' "$untracked"
else
  echo "(none)"
fi

echo
echo "Key paths:"
echo "GEMINI.md"
echo "AGENTS.md"
echo "CLAUDE.md"
echo ".github/copilot-instructions.md"
echo ".github/instructions/*.instructions.md"
echo "docs/production_recovery_living_doc_20260526.md"
echo "docs/runtime_reports/production_recovery_docs_audit_20260526.md"
echo "docs/agent_ops/agent_instruction_audit_20260526.md"
echo "docs/agent_ops/gemini_recovery_workflow.md"
echo "docs/agent_ops/codex_recovery_workflow.md"
echo "docs/agent_ops/chatgpt_session_bootstrap.md"
echo ".gemini/commands/init/*.toml"
echo ".gemini/commands/recovery/*.toml"
echo ".gemini/settings.example.json"
echo "scripts/agent_gate_validate.sh"
echo "scripts/agent_context_bundle.sh"
echo "majorTODO.md"

echo
echo "How to use this bundle:"
echo "Paste this output into a fresh ChatGPT, Gemini, or Codex session before asking for recovery work. Then attach or reference the active recovery doc and the exact gate task. This bundle contains repo paths and status only; it prints no secrets, private keys, production credentials, or auth values."

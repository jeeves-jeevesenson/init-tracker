#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== repo =="
pwd

echo
echo "== branch/status =="
git status --short --branch

echo
echo "== recent commits =="
git log --oneline --decorate -8

echo
echo "== diff stat =="
git diff --stat || true

echo
echo "== important docs present =="
for f in docs/dm_spell_engine_living_plan.md docs/dm_control_surface_living_agent_plan.md AGENTS.md CLAUDE.md GEMINI.md; do
  [ -f "$f" ] && echo "OK $f" || echo "MISSING $f"
done

echo
echo "== untracked agent/tooling files =="
git status --short | grep -E '^\?\? \.antigravitycli/|^\?\? \.agent_bootstrap_backups/' || true

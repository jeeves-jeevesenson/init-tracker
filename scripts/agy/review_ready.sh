#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== status =="
git status --short

echo
echo "== diff stat =="
git diff --stat

echo
echo "== compile/targeted validation =="
scripts/agy/validate_spell_pass.sh

echo
echo "== primitive audit =="
scripts/agy/audit_spell_primitives.sh

echo
echo "== newest runtime reports =="
ls -1t docs/runtime_reports 2>/dev/null | head -12 || true

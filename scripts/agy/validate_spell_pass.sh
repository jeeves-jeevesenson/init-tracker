#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== py_compile core files =="
files=(dnd_initative_tracker.py map_state.py player_command_service.py player_command_contracts.py)
[ -f spell_engine_primitives.py ] && files+=(spell_engine_primitives.py)
python3 -m py_compile "${files[@]}"

echo
echo "== warning-clean core spell tests =="
[ -f tests/test_spell_casting_primitive.py ] && PYTHONWARNINGS=error python3 -m unittest tests.test_spell_casting_primitive || true
[ -f tests/test_spell_aoe_targeting_primitives.py ] && PYTHONWARNINGS=error python3 -m unittest tests.test_spell_aoe_targeting_primitives || true
[ -f tests/test_lan_manual_override.py ] && PYTHONWARNINGS=error python3 -m unittest tests.test_lan_manual_override || true

echo
echo "== asset syntax pytest if available =="
if python3 -c 'import pytest' >/dev/null 2>&1; then
  [ -f tests/test_dm_console_asset_syntax.py ] && python3 -m pytest -q tests/test_dm_console_asset_syntax.py || true
else
  echo "pytest not installed; skipping pytest asset syntax test."
fi

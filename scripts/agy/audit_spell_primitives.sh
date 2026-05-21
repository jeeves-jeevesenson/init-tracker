#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== spell primitive purity check =="
if [ -f spell_engine_primitives.py ]; then
  grep -RIn "_lan_force_state_broadcast\|broadcast\|self\.combatants\|self\._map_window\|self\." spell_engine_primitives.py || true
else
  echo "spell_engine_primitives.py not present"
fi

echo
echo "== spell-name branch smell =="
grep -RIn "fireball\|shatter\|thunderwave\|lightning bolt\|burning hands\|synaptic\|wall of fire\|spell_name ==" dnd_initative_tracker.py spell_engine_primitives.py 2>/dev/null || true

echo
echo "== hot path YAML parsing smell =="
grep -RIn "yaml.safe_load\|yaml.load\|open(.*Spells\|glob.*Spells" dnd_initative_tracker.py spell_engine_primitives.py player_command_service.py 2>/dev/null || true

echo
echo "== hardcoded grid scale smell =="
grep -RIn "FEET_PER_SQUARE\|feet_per_square *= *5\|= *5\.0" dnd_initative_tracker.py spell_engine_primitives.py map_state.py 2>/dev/null || true

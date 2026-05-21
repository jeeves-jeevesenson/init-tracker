Read docs/dm_spell_engine_living_plan.md first.

Implement Pass 4: Persistent concentration / active spell lifecycle.

Allowed files:
- dnd_initative_tracker.py
- player_command_contracts.py
- spell_engine_primitives.py
- assets/web/lan/index.html
- tests/
- docs/runtime_reports/

Ask before touching:
- map_state.py
- combat_service.py
- DM console files
- monster capability files

Required behavior:
1. Persistent concentration AoE creation registers authoritative backend state with caster/spell metadata.
2. New concentration from same caster replaces/removes previous concentration-linked effect.
3. Explicit concentration drop removes linked effect and broadcasts.
4. Reset turn clears local pending state but preserves authoritative concentration unless backend explicitly ends it.
5. Reconnect renders authoritative effects and does not resurrect ghosts.
6. Instant AoEs do not leave persistent effects.

Validation:
- scripts/agy/validate_spell_pass.sh
- scripts/agy/audit_spell_primitives.sh

Report:
docs/runtime_reports/spell_engine_pass4_concentration_lifecycle_YYYYMMDD_HHMM.md

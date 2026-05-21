Read docs/dm_spell_engine_living_plan.md first.

Implement Pass 5: Summon primitive.

Goal:
Summon spells must either create authoritative spawned combatants or create an explicit DM-required pending summon request. No silent placement failures.

Allowed files:
- dnd_initative_tracker.py
- player_command_contracts.py
- assets/web/lan/index.html
- tests/
- docs/runtime_reports/

Required statuses:
- CAST_SUMMON_PENDING_DM
- CAST_SUMMON_CREATED
- CAST_REJECTED

Validation:
- scripts/agy/validate_spell_pass.sh

Report:
docs/runtime_reports/spell_engine_pass5_summon_primitive_YYYYMMDD_HHMM.md

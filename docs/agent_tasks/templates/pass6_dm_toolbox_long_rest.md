Read docs/dm_spell_engine_living_plan.md first.

Implement Pass 6: DM Toolbox Long Rest.

Goal:
Add a DM Toolbox control for long resting players. This must be a real backend rest action, not HP-only.

Expected behavior:
- restore player HP to max
- restore spell slots to max
- restore long-rest resource pools
- clear death saves/turn-local state
- broadcast one authoritative update
- write battle-log entry

Allowed files:
- dnd_initative_tracker.py
- player_command_service.py
- player_command_contracts.py
- assets/web/dm/index.html
- tests/
- docs/runtime_reports/

Validation:
- python3 -m py_compile dnd_initative_tracker.py player_command_service.py player_command_contracts.py
- PYTHONWARNINGS=error python3 -m unittest tests.test_lan_manual_override

Report:
docs/runtime_reports/spell_engine_pass6_dm_toolbox_long_rest_YYYYMMDD_HHMM.md

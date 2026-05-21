# Agent Safety and Scope

Preferred mode:
- Plan mode for architecture/refactor work.
- Fast mode only for tiny localized fixes.

Allowed by default for spell passes:
- dnd_initative_tracker.py
- player_command_service.py
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
- deployment/runtime config files
- production docs
- data files

Never do without explicit request:
- git push
- deployment
- service restarts
- destructive cleanup
- deleting branches
- force-push
- editing secrets
- changing DNS/FQDNs/hostnames/ports

When stuck:
- Stop and report the blocker.
- Do not repeatedly edit tests until they pass.
- Do not continue after context/output-limit warnings.

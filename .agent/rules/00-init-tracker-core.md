# Init Tracker Core Agent Rules

This repo is live-game software. Prefer small, reversible, backend-heavy passes.

Before coding:
- Read docs/dm_spell_engine_living_plan.md for spell work.
- Read docs/dm_control_surface_living_agent_plan.md for /dmcontrol work.
- Run scripts/agy/preflight.sh.
- State exact files you intend to edit.
- State exact validation commands you will run.

Hard rules:
- Do not guess FQDNs, hostnames, ports, hardware, runtime paths, or deployment paths.
- Do not push, deploy, restart services, or change production topology unless explicitly asked.
- Do not start broad cleanup while doing a bounded pass.
- Do not edit unrelated systems.
- Do not hide baseline failures.
- Do not claim tests passed if warnings were emitted.

Stop conditions:
- Output/context limit is hit.
- Same test fails more than twice.
- Tests pass but emit warnings.
- Need files outside allowed list.
- Need to change more than about 250 lines in one large file.
- Uncertain about map units, FQDNs, runtime paths, or schema.
- About to write a per-spell branch ladder instead of a primitive.

Required validation:
- Python edits: python3 -m py_compile on edited Python files.
- Tests must be warning-clean with PYTHONWARNINGS=error.
- JS asset edits must run asset syntax validation or node --check.
- Nontrivial passes must write a runtime report in docs/runtime_reports/.

Never commit:
- .antigravitycli/
- .agent_bootstrap_backups/
- local caches
- secret env files
- throwaway logs unless intentionally promoted to runtime report

Read docs/dm_spell_engine_living_plan.md first.

Task:
<one bounded task>

Allowed files:
- <file>

Do not modify:
- production/deploy files
- unrelated systems

Hard requirements:
- no broad refactor
- no per-spell if/elif ladder unless fixing bad metadata
- no frontend-authoritative spell state
- no YAML parsing in hot spell paths
- no new warnings
- no output/context-limit continuation

Stop conditions:
- same test fails twice
- need files outside allowed list
- tests pass but emit warnings
- output/context limit hit
- implementation exceeds about 250 changed lines in one large file
- uncertain about FQDN/path/runtime/schema assumption

Validation:
- scripts/agy/validate_spell_pass.sh
- scripts/agy/audit_spell_primitives.sh

Deliverables:
- code diff
- tests run
- runtime report under docs/runtime_reports/
- limitations
- stop after summary; do not start next pass

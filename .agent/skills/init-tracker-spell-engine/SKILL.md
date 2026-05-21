---
name: init-tracker-spell-engine
description: Use this skill for init-tracker spell casting, AoE targeting, concentration lifecycle, manual override slots/resources, summons, or LAN spell UI feedback.
---

# Init Tracker Spell Engine Skill

## Always read first

- docs/dm_spell_engine_living_plan.md
- .agent/rules/10-spell-engine-rules.md
- .agent/rules/20-agent-safety-and-scope.md

## Required workflow

1. Run scripts/agy/preflight.sh.
2. Identify exact allowed files.
3. Identify exact validation commands.
4. Make the smallest implementation that satisfies the task.
5. Run scripts/agy/validate_spell_pass.sh.
6. Run task-specific tests.
7. Run scripts/agy/audit_spell_primitives.sh if spell primitive code changed.
8. Write a runtime report under docs/runtime_reports/.
9. Stop. Do not start the next pass.

## Constraints

- Do not add one-off spell branches unless metadata is wrong and documented.
- Do not parse YAML in hot spell paths.
- Do not broadcast from geometry helpers.
- Do not mutate global combat state from primitive helpers.
- Do not silently no-op.
- Do not ignore warnings.
- Do not deploy or push.

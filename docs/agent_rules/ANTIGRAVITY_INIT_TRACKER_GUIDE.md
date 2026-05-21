# Antigravity Guide for Init Tracker

This package provides:
- .agent/rules/
- .agent/workflows/
- .agent/skills/init-tracker-spell-engine/
- scripts/agy/
- docs/agent_tasks/templates/
- docs/runtime_reports/_AGY_RUNTIME_REPORT_TEMPLATE.md

Recommended use:
1. Start AGY in Plan mode for nontrivial changes.
2. Ask it to run /00-preflight.
3. Give it a bounded task with allowed files.
4. Require /10-spell-pass-validate.
5. Require /20-audit-spell-primitives when spell primitives changed.
6. Human reviews and commits.

Do not let AGY do by default:
- push
- deploy
- restart services
- touch production topology
- delete files outside explicit cleanup task
- continue after context/output-limit warnings

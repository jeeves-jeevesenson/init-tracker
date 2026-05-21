# Workflow: audit spell primitives

Run:

    scripts/agy/audit_spell_primitives.sh

Review:
- no new spell-name if ladders
- no broadcasts in primitive helpers
- no mutable InitiativeTracker state inside primitive module
- no hardcoded FEET_PER_SQUARE
- no YAML parsing in hot path helpers

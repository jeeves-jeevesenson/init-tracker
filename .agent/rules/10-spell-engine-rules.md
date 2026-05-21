# Spell Engine Rules

Read docs/dm_spell_engine_living_plan.md before touching spell code.

Architecture:
- Backend owns spell truth.
- Frontend local ghosts/previews are disposable.
- Fix primitives, not spell names.
- Do not create long if/elif ladders for Fireball, Shatter, Thunderwave, etc.
- Spell-specific code is allowed only to fix bad metadata or a truly unique rule, and it must be documented.

Shared spell primitives:
- single-target attack
- single-target save
- multi-target selected spell
- point AoE
- self-origin line/cone/cube
- persistent/concentration AoE
- summon request/spawn
- utility/manual-resolution spell

Performance:
- No YAML parsing in hot cast/resolve paths.
- No repeated full target scans per effect step if one target set can be computed.
- No broadcasts from geometry helpers.
- No snapshot rebuild until mutations are committed.
- Keep geometry helpers pure or near-pure.

Every spell interaction must produce explicit status/feedback:
- CAST_APPLIED
- CAST_CREATED_PERSISTENT_EFFECT
- CAST_NEEDS_MANUAL_DAMAGE
- CAST_NEEDS_TARGET
- CAST_NEEDS_PLACEMENT
- CAST_NO_TARGETS
- CAST_REJECTED
- CAST_CANCELLED
- CONCENTRATION_ENDED
- CONCENTRATION_REPLACED

No silent paths:
- Empty AoE: show “No targets in area.”
- Unsupported automation: show “Manual resolution required.”
- Invalid placement: show rejection reason.
- Boundary no-op: show reason.
- Backend rejects: show exact reason.

Reset-turn rule:
- Reset turn clears local pending spell interaction state.
- Reset turn must not delete authoritative concentration effects unless backend explicitly says so.

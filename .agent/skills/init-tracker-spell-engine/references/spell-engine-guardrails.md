# Spell Engine Guardrails

Current pass order:
1. Spell cast result contract
2. AoE placement/resolution contract
3. Modal/reset/reconnect cleanup
4. Generic AoE target primitives
5. Manual override slot/resource feedback
6. Persistent concentration lifecycle
7. Summon primitive
8. DM Toolbox Long Rest
9. Spell-like reactions/features

Backend authoritative:
- spell result status
- spell resource mutation
- HP/condition mutation
- authoritative AoE/effect state
- concentration state
- summon creation

Frontend local-only:
- hover/preview
- pending targeting UI
- local placement ghost before submission
- modal visibility

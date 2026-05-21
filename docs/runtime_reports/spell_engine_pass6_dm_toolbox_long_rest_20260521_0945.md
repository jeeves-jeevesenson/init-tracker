# Spell Engine Pass 6: DM Toolbox Long Rest 2026-05-21 09:45

## Goal
Implement a DM Toolbox control for long resting players, performing an authoritative backend rest mutation (HP, spell slots, resource pools, turn state).

## Files changed
- `combat_service.py`: Added `long_rest` method to `CombatService`.
- `dnd_initative_tracker.py`: Added `POST /api/dm/combat/long-rest` route and exposed it via `CombatService`.
- `assets/web/dmcontrol/index.html`: Added "Toolbox" button and modal with "Long Rest Players" control.

## Behavior changed
- DM can now trigger a Long Rest for all players from the DM Control surface.
- The rest is authoritative and resets:
    - HP to max.
    - Spell slots to max (updates player YAML and cache).
    - Long-rest resource pools to max (updates player YAML and cache, handles formula evaluation).
    - Turn-local state (actions, bonus actions, reactions, etc.).
    - Ends concentration.
    - Clears temp HP.
- One battle-log entry is written.
- One authoritative broadcast occurs after the rest.
- Structured result with character summary is returned to the DM console.

## Primitive(s) touched
- `rest` (newly formalised in `CombatService`)

## Tester issue(s) addressed
- "Long rest is HP-only or manual": Now automated for HP, spell slots, and resource pools.
- "Resource recovery is invisible/unreliable": Authoritative update ensures all clients see the recovered state.

## Performance notes
- Performs atomic YAML updates for players.
- One broadcast per long-rest action.

## Validation
- `python3 -m py_compile` passed for edited Python files.
- `scripts/agy/validate_spell_pass.sh` passed.
- `tests/test_combat_service_long_rest.py` passed (2 tests).
- `tests.test_lan_manual_override` passed (9 tests).
- Browser JS syntax check passed for `assets/web/dmcontrol/index.html`.

## Known failures / deferred work
- Death saves were not implemented in the current `Combatant` model, so "Clear death saves" is a no-op for now (documented in code).
- UI for choosing specific rest options (scoped to allies/enemies) is deferred; currently defaults to "players only" with all standard D&D long rest resets.

## Next recommended pass
Pass 7: Manual Override spell slots and resources (to ensure individual resource management is also authoritative and flexible).

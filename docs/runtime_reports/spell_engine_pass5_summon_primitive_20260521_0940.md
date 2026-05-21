# Spell Engine Pass 5: Summon Primitive 2026-05-21 09:40

## Goal
Implement authoritative summon spells that either create combatants or request DM approval, ensuring no silent failures.

## Files changed
- `player_command_contracts.py`: Added `spawned_cids` to `spell_cast_result`.
- `dnd_initative_tracker.py`: 
    - Updated `_send_spell_result` to accept `spawned_cids`.
    - Added `_is_summon_auto_spawn_allowed` helper.
    - Updated `_handle_cast_spell_request` and `_handle_cast_aoe_request` to handle summons authoritatively.
- `assets/web/lan/index.html`: Added `CAST_SUMMON_PENDING_DM` to interaction cleanup.

## Behavior changed
- Summon spells now return explicit statuses: `CAST_SUMMON_CREATED` (if spawned), `CAST_SUMMON_PENDING_DM` (if waiting for DM), or `CAST_REJECTED`.
- Players can now trigger summon placement for spells with `summon_config`, and the backend will adjudicate whether to spawn them immediately or mark them as pending DM.
- `spawned_cids` are included in the result payload for `CAST_SUMMON_CREATED`.
- LAN client correctly clears local ghosts after a summon cast completes or is pending DM.

## Primitive(s) touched
- `summon`

## Tester issue(s) addressed
- "Summons do not appear authoritatively": Summon placement now creates authoritative combatants or explicit DM requests.
- No silent failures for summons.

## Performance notes
- No YAML parsing or expensive re-scans added to the hot path.
- One broadcast per summon cast.

## Validation
- `python3 -m py_compile` passed.
- `scripts/agy/validate_spell_pass.sh` passed.
- `tests/test_spell_summon_primitive.py` passed (4 tests).
- Browser JS syntax check passed for `dm/index.html` and `lan/index.html`.

## Known failures / deferred work
- Actual DM UI for approving pending summon requests is not yet implemented (DM currently must manually place/spawn if they see the toast or battle log).
- More complex "controlled" summon behavior (like auto-spawn for specific player features) can be expanded in the `_is_summon_auto_spawn_allowed` helper.

## Next recommended pass
Pass 6: Manual Override spell slots and resources (to ensure resource recovery is visible and reliable).

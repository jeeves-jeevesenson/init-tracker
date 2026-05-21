# Runtime Report: Spell Engine Pass 7B - Hellish Rebuke Reaction

**Date:** 2026-05-21 10:40
**Agent:** Gemini CLI

## Symptom / Scope
Implement Pass 7B: Hellish Rebuke reaction flow using the existing reaction contract. This pass ensures that Hellish Rebuke can be offered as a reaction when a combatant takes damage, and that it resolves correctly with authoritative backend logic and clear frontend feedback.

## Evidence / Research
- `dnd_initative_tracker.py` already contained significant logic for Hellish Rebuke (`_maybe_offer_hellish_rebuke` and `_handle_hellish_rebuke_resolve_request`).
- `player_command_service.py` handled the initial reaction response but delegating resolution to a specialty command.
- `tests/test_hellish_rebuke_reaction.py` existed and covered basic flow but missed visibility and contract builder verification.
- Frontend handling for `hellish_rebuke_result` was missing.
- Frontend handling for `hellish_rebuke_resolve_start` was using `openSpellResolveModal` which prompted for manual damage entries, which the backend ignores.

## Changes
- **player_command_contracts.py**:
  - Added `HELLISH_REBUKE_RESULT_FIELDS`.
  - Added `build_hellish_rebuke_result` helper.
- **player_command_service.py**:
  - Added visibility check to `maybe_offer_hellish_rebuke` using `t._line_of_sight_blocked`.
- **dnd_initative_tracker.py**:
  - Updated `_handle_hellish_rebuke_resolve_request` to use `build_hellish_rebuke_result`.
  - Registered `build_hellish_rebuke_result` in imports.
- **assets/web/lan/index.html**:
  - Added `hellish_rebuke_result` message handler with detailed toast feedback (save results, damage dealt).
  - Streamlined `hellish_rebuke_resolve_start` to only prompt for slot level and avoid the clunky manual resolution modal.
- **tests/test_hellish_rebuke_reaction.py**:
  - Added `test_visibility_blocks_offer` to verify that LOS blockage prevents the reaction offer.

## Validation Results
- `python3 -m unittest tests/test_hellish_rebuke_reaction.py`: **Passed** (8 tests).
- `bash scripts/agy/validate_spell_pass.sh`: **Passed**.
- Mandatory browser JS syntax check: **Passed** for `assets/web/lan/index.html`.

## Risk / Limitations
- Visibility check relies on the current `_lan_live_map_data` obstacles. If obstacles are not up to date, the check might be inaccurate.
- Reaction modes (auto/ask/off) are supported via `_reaction_mode_for`, but "auto" acceptance still uses the default choice.

## Next Broad Pass
Pass 7C: Shield reaction flow stabilization and contract alignment.

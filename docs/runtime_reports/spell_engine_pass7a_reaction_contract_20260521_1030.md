# Spell Engine Pass 7A: Reaction / Trigger Contract 2026-05-21 10:30

## Goal
Add a backend-owned contract for reaction-style spell and feature prompts, ensuring authoritative resolution and clear feedback.

## Files changed
- `player_command_contracts.py`: 
    - Added `REACTION_*` statuses (`ACCEPTED`, `DECLINED`, `EXPIRED`, `REJECTED`).
    - Added `build_reaction_result` function.
- `dnd_initative_tracker.py`:
    - Added `_create_pending_reaction` helper to create and broadcast reaction offers.
    - Added `_send_reaction_result` helper to send structured results via WebSockets.
    - Added `test_reaction_trigger` smoke command to `_lan_apply_action`.
- `player_command_service.py`:
    - Updated `reaction_response` to include resource validation and send `reaction_result`.
    - Implemented generic fallback in `_resolve_reaction_response` for unhandled or generic triggers.
- `assets/web/lan/index.html`:
    - Added handler for `reaction_result` in `processMessage` to clear modal and show toasts.

## Behavior changed
- Backend now authoritatively tracks pending reaction prompts in `_pending_prompts`.
- Players receive structured `reaction_offer` payloads when a reaction is triggered.
- Acceptance of a reaction validates that the reactor exists and has their reaction resource available.
- Rejection or terminal resolution (accept/decline) returns a structured `reaction_result` to the client.
- The LAN client correctly clears reaction modals and displays feedback toasts upon receiving results.
- Expiration of stale offers is explicitly handled during command processing.

## Primitive(s) touched
- `reaction`

## Tester issue(s) addressed
- "Reactions are silent or uncoordinated": Now use a formal contract with explicit results.
- No silent failures for reaction resolution.

## Performance notes
- Uses existing `PromptState` service for efficient pending prompt management.
- Explicit cleanup of expired prompts prevents state bloat.

## Validation
- `python3 -m py_compile` passed for edited Python files.
- `scripts/agy/validate_spell_pass.sh` passed.
- `tests/test_reaction_contract.py` passed (6 tests).
- Browser JS syntax check passed for `assets/web/lan/index.html`.

## Known failures / deferred work
- Special triggers like `Bardic Inspiration` are not yet fully modeled in this generic contract.
- Trigger-specific validation (e.g., "is the attacker still in range?") remains on a per-trigger basis.

## Next recommended pass
Pass 7B: Bardic Inspiration / Mantle of Inspiration full feature work (building on this reaction contract).

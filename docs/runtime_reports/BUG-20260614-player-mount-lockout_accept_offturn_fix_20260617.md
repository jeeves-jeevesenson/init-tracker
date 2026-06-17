# Runtime Report: BUG-20260614-player-mount-lockout_accept_offturn_fix_20260617

## Smoke Failure Summary
Developer smoke testing on 2026-06-17 revealed that John Twilight (the target mount) could not accept Vicnor's mount request because it was not John's turn. The backend rejected the `mount_response` with a "Not yer turn yet, matey." toast. This blocked reproduction of the original rider-follow desync bug.

## Root Cause
The `mount_response` command was included in the `TURN_LOCAL_COMMAND_TYPES` family, but it was not exempted from the turn-gate check in ` InitiativeTracker._lan_apply_action`. Unlike movement or attacks, responding to a mount request often must happen off-turn (when the rider initiates the request on their turn).

## Changes
- **dnd_initative_tracker.py**: Added `mount_response` to the list of commands exempted from the turn-gate check in `_lan_apply_action`.
- **player_command_service.py**: Added a safety check to `mount_response` to verify that the responder's CID matches the intended mount's CID (or is an admin), preventing unauthorized responses.

## Safety Checks Preserved
- Movement remains turn-gated.
- Attacks and other turn-actions remain turn-gated.
- `mount_request` remains turn-gated (rider must initiate on their turn).
- Mount responses are only accepted if a valid pending request exists for that specific mount.

## Test Coverage Added
- **tests/test_mount_response_turn_gate.py**: 
    - `test_mount_response_off_turn_allowed`: Proves that off-turn mount responses now reach the acceptance handler.
    - `test_movement_off_turn_still_blocked`: Proves that movement is still rejected off-turn.

## Validation Results
- `py_compile` passed for both edited files.
- `pytest` was unavailable in the current environment (`No module named pytest`).
- `unittest` validation command: `.venv/bin/python -m unittest discover -s tests -p 'test_mount_response_turn_gate.py' -v`
- `unittest` results: All 6 tests passed (including off-turn allowed, movement blocked, wrong claimant rejected, and admin bypass).

## Next Action
Retry developer smoke:
1. Vicnor (rider) requests to mount John Twilight (mount) on Vicnor's turn.
2. John Twilight accepts the request (now possible off-turn).
3. Continue bottom/top follow trace to investigate the original rider-follow desync.

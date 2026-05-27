# Gate 1 Evidence Report: Map Surface Contract Restoration
Date: 2026-05-26
Task: ITR-20260526-G1-01

## 1. Symptom & Root Cause
- **Symptom**: `/dm/map` and `/dmcontrol` were unable to use map features; tests failed with `AttributeError`.
- **Root Cause**: `_dm_console_snapshot` was a local closure in `LanController.start`, making it inaccessible to tests. Additionally, `/api/dm/combat` was hardcoded to `include_tactical=False`, preventing map workspaces from getting tactical snapshots on initial load or during polling.

## 2. Changes Applied
### dnd_initative_tracker.py
- Refactored `_dm_console_snapshot` from a local closure into a formal method of `LanController`.
- Enhanced `_dm_console_snapshot` to automatically detect tactical requirements via `_current_request_wants_tactical_map()`.
- Updated `/api/dm/combat` to use `_dm_console_snapshot()`, restoring support for `?workspace=map` and `?workspace=dmcontrol` query parameters.

### tests/test_dm_tactical_map_routes.py
- Repaired `_TacticalAppStub` to include missing `CombatService` dependencies (`_next_turn`, `_rebuild_table`, `_broadcast_tracker_state`).
- Corrected test cases that were incorrectly calling `lan._lan_force_state_broadcast()` instead of `lan._tracker._lan_force_state_broadcast()`.
- Updated `_build_lan_controller` to ensure the tracker stub has a back-reference to the `LanController`, enabling realistic broadcast simulation.

## 3. Validation Results
- **Unit Tests**: `python3 -m unittest tests.test_dm_tactical_map_routes` (86 tests) all PASS in the virtual environment.
- **Contract Verification**:
    - `/api/dm/combat` (no workspace) -> Lite snapshot (PASS).
    - `/api/dm/combat?workspace=map` -> Tactical snapshot (PASS).
    - `/api/dm/combat?workspace=dmcontrol` -> Tactical snapshot (PASS).
    - WebSockets with `workspace=map` -> Tactical snapshot (PASS).
    - Broadcast with active map clients -> Tactical snapshot for all DM clients (PASS).

## 4. Residual Risks
- The broadcast logic still sends tactical snapshots to ALL DM clients if AT LEAST ONE map client is connected. While this satisfies the contract, it is a minor performance trade-off for mixed-workspace DM sessions.

No commit, push, deploy, SSH, or service restart performed.

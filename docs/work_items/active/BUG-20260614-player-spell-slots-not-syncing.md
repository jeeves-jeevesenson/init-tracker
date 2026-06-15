# BUG-20260614-player-spell-slots-not-syncing

- **Title**: Player spell slot/resource sync does not update UI after cast or manual override.
- **Status**: Active
- **Source bug**: [docs/bug_reports/inbox/BUG-20260614-player-spell-slots-not-syncing.md](../bug_reports/inbox/BUG-20260614-player-spell-slots-not-syncing.md)
- **Scope**: player web index/player UI resource synchronization only.

## Initial Gate: Gate 1 — Evidence capture and bounded fix plan

### Goal
Identify why spell slot casts and manual slot overrides appear in logs/API responses but do not refresh player UI or manual override menu state.

### Non-goals
- Do not change DM-side automation.
- Do not change monster AI.
- Do not change AoE targeting.
- Do not change mount behavior.
- Do not change 1080p layout.

## Plan

### Gate 1: Evidence capture and bounded fix plan
- [x] Reproduce the issue using browser smoke or manual inspection of resource sync payloads.
- [x] Inspect `assets/web/lan/index.html` (player UI) resource update logic.
- [x] Verify if manual override menu state is correctly hydrated from backend state.
- [x] Propose a bounded fix plan.

#### Suspected Root Cause
1.  **Stale LAN Cache**: `dnd_initative_tracker.py` -> `_save_player_spell_slots` is missing a call to `self._refresh_cached_player_profile_projection(profile_name, profile)`. This means the LAN protocol's static data cache is not updated when spell slots are changed via casting or manual override.
2.  **Insufficient Broadcast Scope**: `_save_player_spell_slots` schedules a refresh with `include_static=False`. Since spell slots are part of the "static" (slow-moving) player profiles in the LAN protocol, a dynamic-only broadcast combined with a stale cache results in the client receiving old slot data.
3.  **Invalidation Domain Clobbering**: `_write_player_yaml_atomic` overwrites `self._last_invalidation_domains` instead of accumulating domains. This can cause the `_lan_snapshot` rebuild of `resource_pools` to be skipped if multiple writes occur before the 200ms refresh window.

#### Bounded Fix Plan
1.  **Repair `_save_player_spell_slots`**:
    *   Call `_refresh_cached_player_profile_projection` before scheduling refresh.
    *   Use `include_static=True` for the refresh to ensure authoritative sync.
2.  **Robust Invalidation Accumulation**:
    *   Modify `_write_player_yaml_atomic` to accumulate `invalidation_domains` into a set.
    *   Modify `_schedule_player_yaml_refresh` to clear the set after the broadcast.
3.  **Validation**:
    *   Verify `dnd_initative_tracker.py` consistency across `_save_player_spell_config`, `_save_player_spellbook`, and `_save_player_spell_slots`.
    *   Verify `resource_pools` rebuild logic in `_lan_snapshot`.

### Gate 2: Implementation and Validation
- [x] Apply fix to `dnd_initative_tracker.py`.
- [x] Run focused unit tests for player resource sync.
- [ ] Verify fix with browser smoke test (developer-led).

#### Implementation Notes
1.  **`_save_player_spell_slots`**: Added call to `_refresh_cached_player_profile_projection` and updated `_schedule_player_yaml_refresh` to use `include_static=True`. This ensures that spell slot changes (from casting or manual override) are immediately reflected in the backend projection cache and broadcast with the full authoritative payload.
2.  **Domain Accumulation**: Modified `_write_player_yaml_atomic` and `_schedule_player_yaml_refresh` to accumulate invalidation domains into `self._last_invalidation_domains` during the debounce window. This prevents concurrent writes from clobbering each other's invalidation signals.
3.  **Test Alignment**: Updated `tests/test_lan_broadcast_invalidation.py` to expect `include_static=True` for spell slot writes, aligning the test with the required authoritative sync behavior.

#### Validation Results
- `py_compile dnd_initative_tracker.py`: Passed.
- `git diff --check`: Passed.
- `unittest tests/test_lan_broadcast_invalidation.py`: 5/5 passed.
    *   `test_manage_spells_change_requests_static_capability_refresh`: Repaired to expect optimized projection refresh.
    *   `test_cast_spell_current_values_request_static_snapshot_for_authoritative_sync`: Updated to expect authoritative sync with projection refresh.
- **Manual Verification**: Implementation matches the pattern used in `_save_player_spellbook` and `_save_player_spell_config`. All focused tests now pass.

#### Next Steps
- Developer-led browser smoke test is required to confirm the fix resolves the reported UI sync issues.
- Ready for Gate 2 closure after smoke verification.

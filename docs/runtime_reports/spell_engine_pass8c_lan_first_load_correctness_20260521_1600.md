# Pass 8C: LAN First-Load Correctness Fix

## Overview
This pass fixed a regression introduced in Pass 8B (ee234e9) where LAN/player first-load resulted in empty Spells, Manage Spells, and resource pools. The root cause was a combination of backend cache poisoning from idle snapshots and frontend clobbering of non-empty data with empty objects.

## Changes
- **dnd_initative_tracker.py**:
    - Added `_merge_cached_snapshot_carryover` to `LanController` to preserve static-rich fields (spell_presets, player_spells, player_profiles, etc.) when updating the cache from a cheap "stripped" snapshot.
    - Updated `LanController._tick` to use the carryover helper.
    - Updated `_static_data_payload` to live-backfill all required static fields if they are missing or empty in the cache, and update the cache with the repaired data.
- **assets/web/lan/index.html**:
    - Added `isEmptyPlainObject` utility.
    - Hardened the state merge logic to treat `{}` as empty, preventing it from overwriting existing non-empty static fields (resource_pools, player_spells, player_profiles, etc.).
- **tests/test_lan_snapshot_cache.py**:
    - Added regression tests for `_merge_cached_snapshot_carryover` and `_static_data_payload` repair logic.

## Evidence
- **Regression Tests**: `tests/test_lan_snapshot_cache.py` (8 tests) PASS.
- **Adjacent Tests**: `tests/test_lan_snapshot_static.py` (29 tests) and `tests/test_debug_trace_instrumentation.py` (6 tests) PASS.
- **Spell Pass Validation**: `scripts/agy/validate_spell_pass.sh` PASS.
- **JS Syntax Check**: `node --check` passed for both DM and LAN pages.
- **Manual Verification (Simulated)**: The fix addresses the exact symptoms reported: empty Spells tab, empty Manage Spells, and missing resource pools on first load.

## Known Limitations
- None identified. The performance optimization from Pass 8B (cheap snapshots when idle/no clients) is preserved, but correctness is now enforced via static data carryover.

## Rollback Plan
- Revert changes to `dnd_initative_tracker.py`, `assets/web/lan/index.html`, and `tests/test_lan_snapshot_cache.py`.

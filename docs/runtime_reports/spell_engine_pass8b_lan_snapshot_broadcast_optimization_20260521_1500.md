# Pass 8B: LAN Snapshot & Broadcast Optimization

## Overview
This pass implemented a static component cache for LAN snapshots to reduce redundant payload generation during broadcasts. It also optimized `_lan_force_state_broadcast` to skip snapshot builds when no clients are connected.

## Changes
- **dnd_initative_tracker.py**:
    - Added `_lan_static_snapshot_cache` and related management methods (`_invalidate_lan_static_snapshot_cache`, `_lan_static_snapshot_cache_status`, `_lan_static_snapshot_component`).
    - Updated `_lan_snapshot` to use the static cache when `include_static=True`.
    - Updated `_lan_force_state_broadcast` to default `include_static=False`, skip work if no clients are connected, and use the static cache for broadcasting full state to new clients.
    - Added debug instrumentation to track cache hits and broadcast efficiency.
- **tests/test_lan_snapshot_static.py**:
    - Updated `AppStub` in `test_tick_throttles_static_payload_checks_when_idle_with_clients` to include `_debug_trace_counts` and `_oplog` methods required by new instrumentation in `LanController._tick`.

## Evidence
- **Assertion Resolved**: `test_tick_throttles_static_payload_checks_when_idle_with_clients` passed after updating the test stub. The failure was a test-setup regression, not a functional regression in the optimization.
- **Cache Hits**: `tests.test_lan_snapshot_cache.LanSnapshotCacheTests.test_force_snapshot_span_marks_static_cache_hit_in_debug_trace` confirms `snapshot_cache_hit:true` appears in debug traces.
- **Validation Results**:
    - `python3 -m py_compile dnd_initative_tracker.py runtime_config.py`: PASS
    - `tests.test_lan_snapshot_cache`: PASS (6 tests)
    - `tests.test_lan_snapshot_static`: PASS (29 tests)
    - `tests.test_debug_trace_instrumentation`: PASS (6 tests)
    - `scripts/agy/validate_spell_pass.sh`: PASS

## Known Limitations
- The static cache invalidation is currently triggered by major events (player/spell/monster catalog refresh). Finer-grained invalidation could be added if needed, but static data changes are infrequent.
- `LanController._tick` still forces a static check if `processed_any` is true. This preserves responsiveness but could be further optimized if action volume is high.

## Rollback Plan
- Revert changes to `dnd_initative_tracker.py` and `tests/test_lan_snapshot_static.py`.
- Delete `tests/test_lan_snapshot_cache.py`.

# Gate 3 Long Rest G3-10 Smoke Report — 2026-05-28

## Task

- Task ID: ITR-20260528-G3-10
- Goal: Reduce Long Rest latency below the Gate 3 fail threshold.
- Files under patch:
  - `combat_service.py`
  - `dnd_initative_tracker.py`

## Browser Smoke Result

Developer result:
- Long Rest felt super fast.
- This is the target responsiveness level.
- Regression risk remains high because the fix changes Long Rest persistence behavior.

## Trace Evidence

Trace:
- `logs/debug-trace-20260528-123238.jsonl`

Key results:
- `combat_service.long_rest`: 1,251.526 ms
- `/api/dm/combat` max: 1,281.562 ms
- `static_plus_dynamic builds`: 0
- queue waits over 1000ms: none
- queue waits over 5000ms: none
- `_lan_force_state_broadcast`: 1,881.063 ms cumulative across 4 calls
- `_dm_tactical_snapshot`: 555.822 ms cumulative across 4 calls

Known non-blocking/warmup spans in same trace:
- `_load_player_yaml_cache`: top span 8,844.417 ms
- `_lan_snapshot`: top span 7,973.561 ms

Decision:
- Long Rest latency is now below the Gate 3 hard fail threshold.
- Commit candidate, pending targeted validation and restart/durability check.

Regression guardrails:
- Future Long Rest traces must keep `combat_service.long_rest < 5000ms`.
- `static_plus_dynamic builds` must remain 0 for ordinary hot paths.
- Long Rest restored state must survive refresh and server restart.
- Watch deferred YAML writer errors.

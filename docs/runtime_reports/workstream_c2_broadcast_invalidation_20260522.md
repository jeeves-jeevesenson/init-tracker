# Workstream C2 — Broadcast Invalidation

## 1. Root Cause Summary
In Workstream C, tracing showed that casting a spell blocked subsequent actions (like movement) for up to 13 seconds. The root cause was `_save_player_spell_slots` implicitly requesting a full static snapshot rebuild (`include_static=True`) via `_schedule_player_yaml_refresh`. This caused the Tk thread to synchronously rebuild the static payload (parsing 395+ spells, 200+ monsters, etc.) every time a spell slot was consumed.

## 2. Exact Old Invalidation Path
1. `_lan_apply_action` -> `_handle_cast_spell_request` -> `self.tracker._save_player_spell_slots`.
2. `_save_player_spell_slots` called `self._write_player_yaml_atomic` which called `self._invalidate_lan_static_snapshot_cache("player_yaml_write")` blindly.
3. `_save_player_spell_slots` called `self._schedule_player_yaml_refresh()` without arguments.
4. `_schedule_player_yaml_refresh()` defaulted to scheduling a background flush with `include_static=True`.
5. The flush ran `_lan_force_state_broadcast(include_static=True)`, spending ~8s parsing files and rebuilding the static dictionaries.

## 3. New Invalidation / Broadcast Classification
The `player_yaml_write` path was refactored to require explicit `invalidation_domains`.
- **Dynamic Only**: Modifying spell slots (`_save_player_spell_slots`) triggers `dynamic_player_values`. The static payload cache is not invalidated, and the flush broadcasts only dynamic state changes.
- **Static**: Changing visual token colors or player prepared spells (`_save_player_spellbook`, `_save_player_token_color`, etc.) triggers `static_capabilities` or `profile_structure`, correctly invalidating the static cache.
- **Trace Support**: Broadcast now traces its exact mode (`static_plus_dynamic`, `dynamic_only`, etc.), `invalidation_domains`, and `invalidation_reason`.

## 4. What Still Triggers Static Rebuild
- First LAN client connection.
- Modifying a player's token color/border or changing prepared/known spells.
- A direct edit to a player's YAML profile that falls back to defaulting to static.
- Leveling up or managing inventory structure.

## 5. What No Longer Triggers Static Rebuild
- Ordinary spell casting (slot consumption).
- HP modification / damage / healing.
- Moving tokens on the map.
- Passing the turn.

## 6. Trace Fields Added
Added to `lan.snapshot.build` and `lan.state.broadcast_completed`:
- `broadcast_kind`: (`dynamic_only`, `static_only`, `static_plus_dynamic`, `first_load_full`)
- `invalidation_domains`
- `invalidation_reason`
- `include_static` (bool)
- `static_payload_rebuild` (bool)
- `dynamic_payload_rebuild` (bool)
- `snapshot_cache_hit` (bool)
- `snapshot_build_ms` (time to run `_lan_snapshot` and dict building)
- `broadcast_ms` (time to dump JSON and push to active websockets)
- `slow_static_payload_rebuild`: True if `snapshot_build_ms` > 500
- `slow_broadcast`: True if `broadcast_ms` > 1000

## 7. Tests Proving Dynamic Actions Avoid Static Rebuild
- `test_cast_spell_current_values_do_not_request_static_snapshot`: Confirms `_save_player_spell_slots` does not invalidate static cache and only schedules dynamic refresh.
- `test_manage_spells_change_requests_static_capability_refresh`: Confirms modifying the spellbook directly continues to trigger a static rebuild.
- `test_broadcast_trace_records_kind_and_invalidation_domains`: Verifies the new trace tags propagate down through `_lan_force_state_broadcast`.

## 8. Remaining Risks / C3 Recommendation
Currently, dynamic actions are fully unblocked from the static payload bottleneck. However, if a user *does* change their prepared spells during combat, the resulting static broadcast will still lock the main Tk thread for ~8 seconds.
If this latency is unacceptable for the `Manage Spells` UI usage, a subsequent Workstream C3 pass would be required to move static serialization to a background thread. For now, combat action flow is fast and fluid.

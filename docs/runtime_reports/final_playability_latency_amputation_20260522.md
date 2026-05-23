# Final Playability Latency Amputation

Date: 2026-05-22

## User Smoke Verdict

The latest user smoke reported that functionality is materially improved, but the app is still not playable because ordinary actions randomly queue behind 10-20s server work. Users interpret the delay as failure and click repeatedly, causing more backlog. The release blocker is responsiveness, not another frontend processing indicator.

## Trace Summary

Source: `logs/debug-trace-20260522-211827.jsonl`

`scripts/trace_latency_summary.py` reports:

- Top cumulative spans: `_lan_snapshot` 641577.655ms, `http.request` 344199.056ms, `_dm_console_snapshot_payload` 244915.600ms, `_dm_tactical_snapshot` 234547.875ms, `_lan_force_state_broadcast` 175130.917ms, `lan.snapshot.build` 169703.837ms.
- Worst spans: `/api/dm/combat/long-rest` HTTP span 33113.388ms, `combat_service.long_rest` 32788.319ms, `_lan_force_state_broadcast` 19263.882ms, `lan.snapshot.build` 19188.713ms, `_lan_snapshot` 19188.158ms.
- Top queue waits: `manual_override_resource_pool` 23681.404ms, `reaction_prefs_update` 22580.063ms, `end_turn` 20044.714ms, `move` over 20s in the same blocked window, `attack_request` over 8s.
- `static_plus_dynamic` builds: 11.
- `_dm_tactical_snapshot`: 415 calls, 234547.875ms cumulative.
- `/api/dm/combat`: 395 traced request spans, 304539.664ms cumulative, 770.986ms average, 33113.388ms max.

## Decision

Tactical map, ship, surface, structure, and boarding projections are experimental for this playable release. They are now default-off in the normal runtime unless explicitly enabled:

- `INIT_TRACKER_ENABLE_TACTICAL_MAP=1`
- `INIT_TRACKER_ENABLE_SHIP_SURFACES=1`

Normal combat must be combat-lite. The default `/api/dm/combat` polling path returns the combat snapshot only and does not build `_dm_tactical_snapshot`. Explicit `/dm/map` and map mutation routes remain available and still return tactical snapshots for map-authoring workflows.

## Files Changed

- `runtime_config.py`
- `dnd_initative_tracker.py`
- `combat_service.py`
- `scripts/trace_latency_summary.py`
- `tests/test_dm_tactical_map_routes.py`
- `tests/test_lan_attack_request.py`
- `tests/test_lan_broadcast_invalidation.py`
- `tests/test_lan_snapshot_static.py`
- `tests/test_trace_latency_summary.py`
- `docs/init_tracker_production_living_doc.md`
- `init_tracker_production_living_doc.md`
- `majorTODO.md`

## Behavior Changes

- `/api/dm/combat` no longer includes `tactical_map` by default and does not call `_dm_tactical_snapshot`.
- LAN dynamic snapshots skip ship/surface/structure/boarding projection work unless `INIT_TRACKER_ENABLE_SHIP_SURFACES=1`.
- DM websocket pushes from normal LAN broadcasts no longer synthesize tactical snapshots unless `INIT_TRACKER_ENABLE_TACTICAL_MAP=1`.
- LAN tick no longer runs a static payload comparison immediately after every processed action; static checks are periodic or tied to actual static invalidation.
- Resource pool current-value writes use dynamic/resource invalidation and dynamic-only refresh, not static refresh.
- Long rest now broadcasts dynamic/combat-lite state rather than `include_static=True`; long-rest resource semantics were not otherwise expanded in this pass.
- `reaction_prefs_update` is applied directly as coalesced last-write-wins state and does not enter the combat action queue or trigger a broadcast.
- Duplicate pending `manual_override_resource_pool` updates from the same websocket/cid/pool/delta skip stale queued entries so the final duplicate survives after lag.
- Echo/unleash attack requests that ask for `unarmed_strike` inherit the owner's equipped/configured non-unarmed weapon. Trace fields now include `source_actor_cid`, `owner_cid`, `echo_cid`, `requested_weapon_id`, `resolved_owner_weapon_id`, `final_weapon_id`, `echo_weapon_inherited`, and `fallback_reason`.

## Tests Added Or Updated

- DM combat lite/tactical-disabled coverage in `tests/test_dm_tactical_map_routes.py`.
- Echo/unleash unarmed override coverage in `tests/test_lan_attack_request.py`.
- Dynamic resource pool invalidation coverage in `tests/test_lan_broadcast_invalidation.py`.
- Ship/surface tests now explicitly opt into `INIT_TRACKER_ENABLE_SHIP_SURFACES`.
- Trace summary coverage in `tests/test_trace_latency_summary.py`.

## Validation

- `./.venv/bin/python3 -m py_compile character_autofill.py combat_service.py combatant_name_service.py dnd_initative_tracker.py helper_script.py map_state.py monster_capability_service.py player_command_contracts.py player_command_service.py runtime_config.py serve_headless.py ship_blueprints.py spell_engine_primitives.py tk_compat.py update_checker.py scripts/trace_latency_summary.py` passed.
- `./.venv/bin/python3 -m unittest tests.test_items_weapon_resolution` passed.
- `./.venv/bin/python3 -m unittest tests.test_lan_snapshot_cache` passed.
- `./.venv/bin/python3 -m unittest tests.test_lan_snapshot_static` passed.
- `./.venv/bin/python3 -m unittest tests.test_lan_action_safety` passed with the pre-existing coroutine RuntimeWarning.
- `./.venv/bin/python3 -m unittest tests.test_lan_broadcast_invalidation` passed.
- `./.venv/bin/python3 -m unittest tests.test_lan_inventory_responsiveness` passed.
- `./.venv/bin/python3 -m unittest tests.test_lan_movement_action_dispatch` passed.
- `./.venv/bin/python3 -m unittest tests.test_dm_tactical_map_routes` passed.
- `./.venv/bin/python3 -m unittest tests.test_trace_latency_summary` passed.

## Remaining Slow Paths

- Startup/full static hydration can still be expensive.
- Explicit `/dm/map` when used still builds tactical projections by design.
- Explicit Manage Spells/static catalog changes can still require static payload work.
- Long rest may still be semantically heavy and writes several player YAMLs; this pass only removed the release-blocking static/tactical broadcast from the end of the flow.

## Final Smoke Checklist

Use normal `/dm` and LAN pages, not `/dm/map` unless explicitly testing it. Hard-refresh clients, claim 2-3 players, move, set facing, attack, end turn, cast one heavier spell then immediately move, manually override one resource once, toggle reaction prefs, and confirm John Echo/Unleash uses Hellfire Battleaxe rather than Unarmed Strike.

After smoke, run `scripts/trace_latency_summary.py` on the new debug trace and confirm zero ordinary `static_plus_dynamic` builds, zero `_dm_tactical_snapshot` calls from the `/api/dm/combat` default path, no ordinary `queue_wait_ms >5000`, and clear trace reasons for any action over 1000ms.

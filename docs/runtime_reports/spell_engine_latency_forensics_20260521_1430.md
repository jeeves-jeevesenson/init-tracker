# Spell Engine Latency Forensics

Date: 2026-05-21 14:30 America/Chicago

Scope: analysis of the completed live-test debug capture and its startup probes. No gameplay code, frontend asset, runtime configuration, or log files were changed.

## Executive Summary

The live tester trace is `logs/debug-trace-20260521-123648.jsonl`. It is both the newest trace and the largest trace at 65 MB, 197,711 JSONL events, 883 action IDs, and about 104.7 minutes of trace time. Its matching console log is `logs/live-debug-console-20260521-123648.log`. The smaller traces are cold-start probes or near-empty:

| Trace | Events | Role in this report |
|---|---:|---|
| `logs/debug-trace-20260521-123648.jsonl` | 197,711 | Live gameplay trace. Use for gameplay conclusions. |
| `logs/debug-trace-20260521-123501.jsonl` | 569 | Pre-smoke startup trace with no correlated user actions. Use only for startup comparison. |
| `logs/debug-trace-20260521-123300.jsonl` | 1 | Incomplete startup trace. Exclude from conclusions. |
| `logs/debug-trace-20260521-123205.jsonl` | 26 | Startup-only trace with no correlated user actions. Use only for startup comparison. |

Top five bottlenecks, ranked by evidence:

1. Forced LAN state rebuilds dominate interactive hangs. `lan.snapshot.build` ran 49 times with 4,535.043 ms average and 11,745.226 ms worst duration. `_lan_force_state_broadcast` has the same shape at 49 runs, 4,602.968 ms average, and 11,903.442 ms worst duration. Slow `cast_spell`, `set_facing`, summon, dismiss, and wild-shape actions all sit on this path.
2. Background LAN snapshot work is extremely frequent. `_lan_snapshot` completed 32,993 times, consumed 1,988,181.613 ms summed inclusive span time, produced 5,593 `slow.span` rows, 104 `very_slow.span` rows, and 36 `hang_candidate.span` rows. Only 567 `_lan_snapshot` span completions have an `action_id`; the rest are background or uncorrelated snapshot work.
3. Some rejected spell target requests are themselves multi-second waits. After slow casts, `spell_target_request` rejections for `shield`, `blindness-deafness`, and `mage-armor` took 2.1 to 3.1 seconds with no broadcast work under those action IDs.
4. DM control polling is a sustained secondary load. The trace has 511 `GET /api/dm/combat` requests at 203.158 ms average and 1,651.417 ms worst duration. `_dm_console_snapshot_payload` ran 578 times at 178.433 ms average and `_dm_tactical_snapshot` ran 531 times at 169.591 ms average.
5. YAML persistence is visible but not the main 8 to 13 second culprit. `_store_character_yaml` ran seven times at 548.233 ms average and 946.301 ms worst duration. `_load_player_yaml_cache` has one 9,836.800 ms cold-start load and then a very large count of usually cheap calls, including repeated calls inside snapshot-heavy actions.

Top five affected user actions by root websocket dispatch duration:

| Rank | Action | Duration | Action ID | Why it matters |
|---|---|---:|---|---|
| 1 | `cast_spell` for `shield` | 13,831.611 ms | `action-929448efba6a4769a65a647538063321` | A reaction spell cast can appear hung for about 14 seconds before follow-up targeting. |
| 2 | `wild_shape_apply` | 12,988.962 ms | `action-806fb8b451e04ebf984ea1fb0f51a119` | Non-spell state mutation shares the same broadcast/snapshot hang. |
| 3 | `cast_spell` for `toll-the-dead` | 11,919.202 ms | `action-fe34e65255d7407c9607e3a0b8e9beb9` | Normal combat spell selection stalls before target flow. |
| 4 | `cast_spell` for `mage-armor` | 11,441.589 ms | `action-bc20bfaf00314ffc803d2e582419d0de` | The slow path is not limited to damage or AoE spells. |
| 5 | `cast_spell` for `fire-bolt` | 11,416.570 ms | `action-61ce49d033d54548bc668b6e5c6d8a6d` | A basic cantrip hits the same state rebuild bottleneck. |

This is both startup and gameplay latency, but they must not be conflated. Startup-only probes already showed the cold `_load_player_yaml_cache` load and first empty LAN snapshot/broadcast taking around 8.6 to 9.8 seconds with zero combatants and zero websocket clients. The live trace repeats action-correlated 8 to 13 second hangs during gameplay after combat has started, with 13 combatants and one LAN websocket client. The high-confidence gameplay bottleneck is therefore the forced state rebuild path, not just cold start.

Do not chase these first:

- Do not treat AoE target geometry as the latency root cause. `_map_spell_effect_targets` is sub-millisecond to 1.021 ms in this trace. It fails with `AttributeError` for six AoE attempts, which is a correctness bug, not an expensive resolution path.
- Do not start with movement/Dijkstra optimization. No `dijkstra` span appears. The observed movement cost spans are 11 `_lan_shortest_cost` calls at 40.484 ms average and 90.504 ms worst.
- Do not blame LAN send fanout first. Every completed LAN broadcast had one recipient and zero failed sends. The slow spans are before the cheap one-recipient send.
- Do not optimize `long_rest` or `manual_override` from this trace. Exact searches found neither flow in the live trace or matching console log.
- Do not use the analyzer's per-action summed span totals as exclusive wall time. Those totals double-count nested spans.

## Files And Method

Files inspected:

- `docs/runtime_reports/spell_engine_latency_debugging_runbook_20260521_1213.md`
- `docs/dm_spell_engine_living_plan.md`
- `docs/dm_control_surface_living_agent_plan.md`
- `.agent/rules/00-init-tracker-core.md`
- `.agent/rules/20-agent-safety-and-scope.md`
- `scripts/analyze_debug_trace.py`
- `majorTODO.md` latency and snapshot references
- `logs/debug-trace-20260521-123648.jsonl`
- `logs/debug-trace-20260521-123501.jsonl`
- `logs/debug-trace-20260521-123300.jsonl`
- `logs/debug-trace-20260521-123205.jsonl`
- `logs/live-debug-console-20260521-123648.log`
- `logs/live-debug-console-20260521-123501.log`
- `logs/analysis-debug-trace-20260521-123205.txt`

`majorTODO.md` already marks startup/request latency and tactical snapshot/build/broadcast cost as active stabilization work. This report adds live evidence for the same hotspot rather than creating a new architecture claim.

Required inventory and analyzer commands were run as requested. Each candidate trace was analyzed with:

```bash
python3 scripts/analyze_debug_trace.py <trace>
```

The required trace extraction command was run for each trace:

```bash
grep -Ei "slow.span|very_slow.span|hang_candidate|traceback|exception|error|broadcast|snapshot|spell|reaction|aoe|summon|long_rest|yaml|dijkstra|movement" <trace> | tail -1000
```

Additional JSONL grouping was done with temporary `python3 - <<'PY'` snippets only. No helper analysis script was created.

## Evidence Table

Durations are inclusive span durations unless the row says route or root dispatch. Nested span rows explain the same wait; they are not independent root causes.

| Rank | Span/action | Worst duration | Average duration | Count | Action/route/command | Trace/action IDs | User-visible symptom likely caused | Evidence line/event references |
|---|---|---:|---:|---:|---|---|---|---|
| 1 | Root dispatch `cast_spell` for `shield` | 13,831.611 ms | Per action | 1 | `ws.action.dispatch.end`, `cast_spell` | Trace `trace-a57815d8004545c7a86a0b84da0a00bd`, action `action-929448efba6a4769a65a647538063321` | Shield cast looks frozen before next prompt/result. | Live trace line 95576; child `_handle_cast_spell_request` lines 95570-95573. |
| 2 | Forced state broadcast | 11,903.442 ms | 4,602.968 ms | 49 | `_lan_force_state_broadcast`, mostly action mutation path | Worst action `action-fe34e65255d7407c9607e3a0b8e9beb9` | Mutation click blocks on state refresh. | Live trace lines 90384 and 90392; analyzer repeated-span summary. |
| 3 | LAN state snapshot build | 11,745.226 ms | 4,535.043 ms | 49 | `lan.snapshot.build`, command `state` | Worst action `action-fe34e65255d7407c9607e3a0b8e9beb9` | Spell, facing, summon, and wild-shape actions wait on snapshot build. | Live trace lines 90300-90304; each build has `snapshot_cache_hit:false`. |
| 4 | Background LAN snapshot | 11,762.942 ms | 60.261 ms | 32,993 | `_lan_snapshot` | Worst row has no action ID | Periodic latency pressure and uncorrelated stalls while UI is open. | Live trace line 39789; threshold counts show 5,593 slow and 36 hang candidates. |
| 5 | Spell cast service span | 13,830.609 ms | 4,624.044 ms | 29 | `player_command.cast_spell` | Worst `shield` action above | Spell selection itself stalls, including cantrips and reaction spells. | Live trace lines 45939-45942, 95570-95573; analyzer spell summary. |
| 6 | Rejected spell target request | 3,128.210 ms | 710.626 ms | 44 | `player_command.spell_target_request` | Worst `shield` target action `action-4f34c5d5bf6c4234a06c724aa8677cc1` | Invalid target clicks can feel like additional hangs after a cast. | Live trace lines 95697-95701; result `REJECTED`. |
| 7 | DM combat poll route | 1,651.417 ms | 203.158 ms | 511 | `GET /api/dm/combat` | Worst action `action-fb5cca6813be45ed88f2991b0012291b` | DM control surface refresh can lag independently of LAN action dispatch. | Live trace line 90198; route timing summary. |
| 8 | DM console snapshot payload | 1,644.105 ms | 178.433 ms | 578 | `_dm_console_snapshot_payload` | Worst action `action-fb5cca6813be45ed88f2991b0012291b` | DM page polling waits on snapshot packaging. | Live trace line 90194. |
| 9 | DM tactical snapshot | 1,601.343 ms | 169.591 ms | 531 | `_dm_tactical_snapshot` | Worst action `action-fb5cca6813be45ed88f2991b0012291b` | DM tactical refresh stalls next poll/paint. | Live trace line 90192. |
| 10 | Character YAML store | 946.301 ms | 548.233 ms | 7 | `_store_character_yaml` | Worst `lay_on_hands_use` action `action-3baa5bbebdf74c72bf1f1fd412204a16` | Secondary mutation delay when persistence writes happen inline. | Live trace lines 33718 and 45836; YAML write list below. |
| 11 | AoE target mapping failure | 1.021 ms | 0.440 ms | 6 | `_map_spell_effect_targets` | `cast_aoe` for `shatter`, `fireball`, `lightning-bolt`, `wall-of-fire` | Silent/broken AoE resolution, not a latency bottleneck. | Live trace lines 137258-137262, 149184-149189, 154568-154572, 161611-161615. |
| 12 | DM broadcast snapshot failure | No duration emitted | No duration emitted | 47 | `broadcast.end`, span `dm.broadcast.snapshot` | Multiple mutation actions | DM broadcast side can fail while LAN side reports success. | Live trace lines 6422, 8921, 95600; grouped `TypeError` count 47. |

## Timeline

Trace timestamps below are UTC from JSONL. Console log timestamps are America/Chicago. Only events present in logs are included.

| Time | Observed event | Evidence and latency relevance |
|---|---|---|
| 2026-05-21 12:36:49 CDT / 17:36:49Z | Headless start begins. | Console startup begins; live trace line 1 starts `_load_player_yaml_cache`. |
| 17:36:58.903Z | Cold YAML cache load finishes. | `_load_player_yaml_cache` takes 9,836.800 ms with zero combatants and zero websocket clients, live trace lines 1-3. |
| 17:37:07.526Z | First expensive LAN snapshot finishes. | `_lan_snapshot` takes 8,619.319 ms and `lan.snapshot.build` takes 8,619.715 ms before any client is connected, lines 21-24. `_lan_force_state_broadcast` finishes at 8,723.680 ms on line 25. |
| 12:41:47 CDT / 17:41:47Z | First player page load and first LAN websocket connection. | `GET /` lines 1491-1494; console says LAN session connected. |
| 17:41:50Z | DM page loads. | `GET /dm` lines 1584-1587. |
| 17:41:52Z | `/dmcontrol` loads. | `GET /dmcontrol` lines 1698-1701. |
| 17:44:41Z | Combat starts. | `POST /api/dm/combat/start` line 8924. DM broadcast snapshot already emits a `TypeError` on line 8921 while LAN state broadcast is OK. |
| 17:45:36Z through 18:03:46Z | Turn advancement and ordinary combat actions. | `end_turn`, `move`, and `attack_request` dispatches appear. Ordinary moves are mostly 1 to 93 ms. Attack requests are mostly around 184 to 363 ms. |
| 12:45:09 CDT onward | Player reconnect/reload churn. | Console shows repeated disconnect/connect/claim restoration events at 12:45:09, 12:46:25, 12:47:47, 12:49:00, 12:49:57, and later. Trace has repeated `GET /` page loads. |
| 17:50:49Z | First observed summon control hang. | `echo_summon` dispatch takes 8,712.731 ms, action `action-db2447fb4d89498c9a39511be3ef4f1e`, line 26749. |
| 17:51:03Z | Summon dismissal hang. | `dismiss_summons` dispatch takes 8,565.839 ms, action `action-9ec1f920e5e34857b1eb5b7635d9fcc9`, line 27016. |
| 12:52:31 CDT / 17:52:31Z | Attack failure with traceback. | Console traceback shows `KeyError: 'weapon_name'`. Trace lines 29683-29689 mark attack spans `ok:false` and root dispatch `ok:false`. |
| 17:55:46Z | Wild shape hang. | `wild_shape_apply` takes 12,988.962 ms, action `action-806fb8b451e04ebf984ea1fb0f51a119`, line 39165. It contains two forced state broadcasts and one 809.716 ms YAML write. |
| 17:59:03Z | Hellish Rebuke cast. | `cast_spell` for `hellish-rebuke` takes 9,727.144 ms, action `action-bf98e11b21cd4a649975e79c0cae1365`, line 45945. Target request follow-ups take 105.164, 945.713, and 470.518 ms in child service spans. |
| 17:59:03Z | Reaction offer attempt. | `player_command.create_reaction_offer.dispatch` is 0.374 ms, line 45956. Console at 12:59:03 says a counterspell offer was skipped because `ws_ids=[]`. |
| 18:08:00Z through 18:23:32Z | Spell cast hang cluster. | Slow `cast_spell` actions for `chill-touch`, `eldritch-blast`, `fire-bolt`, `mage-hand`, `message`, `shocking-grasp`, `toll-the-dead`, `mage-armor`, `shield`, and `blindness-deafness` land on forced state snapshot rebuilds. |
| 18:20:57Z | Shield hang. | `cast_spell` for `shield` takes 13,831.611 ms. Rejected `shield` target actions then take 3,129.338 and 2,820.532 ms. |
| 18:46:11Z | First observed AoE attempt in the late trace segment. | A slow preceding `set_facing` dispatch takes 8,884.913 ms. The following `cast_aoe` for `shatter` takes 42.338 ms but child AoE mapping fails with `AttributeError`. |
| 18:49:18Z through 19:01:12Z | Further AoE attempts. | `shatter`, `fireball`, `glyph-of-warding`, `lightning-bolt`, and `wall-of-fire` appear. Six target-mapping child spans fail with `AttributeError`; console warns that the handler raised `'NoneType' object has no attribute 'normalized'`. |
| 19:00:18Z and 19:00:25Z | Summoning spell casts appear. | `summon-construct` casts are 14.243 and 14.090 ms. |
| 19:03:22Z | Create Undead appears. | `create-undead` cast is 14.807 ms. |

Not observed in the analyzed logs:

- No `manual_override` string or command was found.
- No `long_rest` string or command was found.
- No explicit Hellish Rebuke or Shield reaction response/resolve command appears.
- `pending_reaction_count` never rises above zero.

## Action-Level Breakdown

The high-latency actions below use root websocket dispatch duration as total duration. Child durations are inclusive and nested.

| Action ID | Command/action | Route/page if known | Total duration | Slow child spans | Repeated child spans | Broadcast count | Snapshot count | YAML/cache count | Suspected root cause |
|---|---|---|---:|---|---|---:|---:|---:|---|
| `action-929448efba6a4769a65a647538063321` | `cast_spell`, `shield` | LAN websocket | 13,831.611 ms | `_handle_cast_spell_request` 13,830.024 ms; `_lan_force_state_broadcast` 11,268.401 ms; `lan.snapshot.build` 11,176.985 ms | `_load_player_yaml_cache` 43 times | 3 | 5 | 43 | Spell waits mostly on forced full state snapshot rebuild. |
| `action-806fb8b451e04ebf984ea1fb0f51a119` | `wild_shape_apply` | LAN websocket | 12,988.962 ms | `_lan_force_state_broadcast` max 11,752.162 ms; `lan.snapshot.build` max 11,633.054 ms; `_store_character_yaml` 809.716 ms | Two forced broadcasts; `_load_player_yaml_cache` 81 times | 5 | 10 | 82 | Duplicate forced state refreshes plus persistence subcost. |
| `action-fe34e65255d7407c9607e3a0b8e9beb9` | `cast_spell`, `toll-the-dead` | LAN websocket | 11,919.202 ms | `_lan_force_state_broadcast` 11,903.442 ms; `lan.snapshot.build` 11,745.226 ms | `_load_player_yaml_cache` 41 times | 3 | 5 | 41 | Snapshot rebuild is almost the whole click. |
| `action-bc20bfaf00314ffc803d2e582419d0de` | `cast_spell`, `mage-armor` | LAN websocket | 11,441.589 ms | `_lan_force_state_broadcast` 9,238.969 ms; `lan.snapshot.build` 9,122.737 ms | `_load_player_yaml_cache` 43 times | 3 | 5 | 43 | Snapshot rebuild plus additional cast path time. |
| `action-61ce49d033d54548bc668b6e5c6d8a6d` | `cast_spell`, `fire-bolt` | LAN websocket | 11,416.570 ms | `_lan_force_state_broadcast` 11,401.088 ms; `lan.snapshot.build` 11,307.739 ms | `_load_player_yaml_cache` 41 times | 3 | 5 | 41 | Cantrip proves bottleneck is shared refresh cost, not spell complexity. |
| `action-bf98e11b21cd4a649975e79c0cae1365` | `cast_spell`, `hellish-rebuke` | LAN websocket | 9,727.144 ms | `_lan_force_state_broadcast` 8,773.554 ms; `lan.snapshot.build` 8,656.134 ms; `_store_character_yaml` 482.581 ms | `_load_player_yaml_cache` 44 times | 3 | 5 | 45 | Shared state rebuild plus persistence write. |
| `action-db2447fb4d89498c9a39511be3ef4f1e` | `echo_summon` | LAN websocket | 8,712.731 ms | `_lan_force_state_broadcast` 8,705.730 ms; `lan.snapshot.build` 8,589.988 ms | `_load_player_yaml_cache` 42 times | 3 | 5 | 42 | Summon control mutation shares same full state refresh. |
| `action-9ec1f920e5e34857b1eb5b7635d9fcc9` | `dismiss_summons` | LAN websocket | 8,565.839 ms | `_lan_force_state_broadcast` 8,564.931 ms; `lan.snapshot.build` 8,448.308 ms | `_load_player_yaml_cache` 40 times | 3 | 5 | 40 | Dismiss path waits on refresh, not summon-specific logic. |
| `action-7c8708b953054342874edcc23fec802b` | `set_facing` | LAN websocket | 8,996.203 ms | `_lan_force_state_broadcast` 8,995.532 ms; `lan.snapshot.build` 8,882.135 ms | `_load_player_yaml_cache` 40 times | 3 | 5 | 40 | Facing change should be cheap but pays full state refresh. |
| `action-4f34c5d5bf6c4234a06c724aa8677cc1` | `spell_target_request`, `shield`, result `REJECTED` | LAN websocket | 3,129.338 ms | `player_command.spell_target_request` 3,128.210 ms | `_load_player_yaml_cache` 3 times | 0 | 0 | 3 | Rejection/validation path has its own latency after the cast hang. |

The repeated `broadcast count = 3` pattern for slow cast/facing/summon actions is one LAN `static_data` payload broadcast, one LAN `state` broadcast, and one failed `dm.broadcast.snapshot` row. The failed DM broadcast row carries no duration.

## Startup Versus Gameplay

Startup facts:

- `logs/debug-trace-20260521-123205.jsonl` shows `_load_player_yaml_cache` at 9,831.824 ms, `_lan_force_state_broadcast` at 8,727.792 ms, `lan.snapshot.build` at 8,626.047 ms, and `_lan_snapshot` at 8,625.714 ms. There are no correlated actions.
- `logs/debug-trace-20260521-123501.jsonl` shows the same cold-start family: `_load_player_yaml_cache` at 11,933.434 ms, `_lan_force_state_broadcast` at 8,777.315 ms, `lan.snapshot.build` at 8,674.541 ms, and `_lan_snapshot` at 8,674.196 ms. There are no correlated actions.
- The live trace starts the same way. Lines 1-25 show the 9,836.800 ms YAML load and 8,619 to 8,723 ms empty LAN snapshot/broadcast before a websocket client connects.

Gameplay facts:

- In the live trace, expensive snapshot rebuilds recur with combatant counts of 13 and one connected LAN websocket client.
- 23 root websocket dispatches exceed 2 seconds in the top action table before reaching the slower target-request rows. They include `cast_spell`, `wild_shape_apply`, `set_facing`, `echo_summon`, and `dismiss_summons`.
- Slow gameplay mutation examples have an action ID, trace ID, and nested `lan.snapshot.build` child. Startup probes do not.

Conclusion: cold start is real, but it does not explain the gameplay hangs. Do not close the latency issue after improving only cold cache load.

## Snapshot And Broadcast Analysis

Observed snapshot counts:

| Work item | Count | Average | Worst | Action IDs present |
|---|---:|---:|---:|---:|
| `_lan_snapshot` | 32,993 | 60.261 ms | 11,762.942 ms | 567 |
| `lan.snapshot.build` | 49 | 4,535.043 ms | 11,745.226 ms | 45 |
| `_dm_console_snapshot_payload` | 578 | 178.433 ms | 1,644.105 ms | 567 |
| `_dm_tactical_snapshot` | 531 | 169.591 ms | 1,601.343 ms | 522 |
| `combat_service.combat_snapshot` | 601 | 21.144 ms | 259.649 ms | Not grouped here |

Findings:

- One slow user action does trigger multiple snapshot families. The slow cast/facing/summon actions above show five snapshot-related span completions each: LAN snapshot build plus DM console/tactical snapshot work. `wild_shape_apply` shows ten because it contains two forced state refreshes.
- LAN and DM snapshot work both appear around action refreshes. The LAN state broadcast can succeed while `dm.broadcast.snapshot` emits `TypeError`.
- Force broadcasts are too expensive to be frequent. There are 49 `_lan_force_state_broadcast` span completions and 49 `lan.snapshot.build` completions. They align closely enough to treat the forced refresh as the root span family.
- Force state work is performed even with no websocket clients during startup. Live trace line 25 shows an 8,723.680 ms `_lan_force_state_broadcast` completion with `websocket_client_count:0`. Completed `broadcast.end` rows themselves always have one LAN recipient; the wasted cold-start work happens before a completed send row exists.
- Cache reuse is partial. Every `lan.snapshot.build` span has `snapshot_cache_hit:false`. Every completed `lan.broadcast.state` row has `snapshot_cache_hit:true`, which means the send reused a built snapshot but the forced build itself did not hit cache.
- Snapshot send size correlates with LAN state send duration, but not with the 8 to 13 second rebuilds. The 47 `lan.broadcast.state` sends range from 58,599 to 265,096 bytes and 2.769 to 51.706 ms with Pearson correlation about 0.79. The 23 `static_data` sends are all 1,227,501 bytes and take 71.648 to 107.444 ms. The state build spans have no emitted `sizes` fields, and their seconds-long cost dwarfs one-recipient send time.
- Static data is repeatedly sent on the slow action family. It is not the dominant wall time, but re-sending a 1.2 MB payload for cast/facing/summon refreshes is worth challenging after the full rebuild is removed from the hot path.

## YAML And Cache Analysis

Observed YAML/cache counts:

| Span | Count | Average | Worst | Main interpretation |
|---|---:|---:|---:|---|
| `_load_player_yaml_cache` | 58,269 | 1.013 ms | 9,836.800 ms | Cold load is huge; repeated revalidation/cache touch is very frequent. |
| `_store_character_yaml` | 7 | 548.233 ms | 946.301 ms | Some mutation paths persist character state inline. |

The expensive first `_load_player_yaml_cache` in the live trace is startup-only at trace line 2. Later cache loads are usually cheap but not free. They appear constantly under snapshots and 40 to 81 times under the slow actions listed above. Later cache load outliers include 1,700.485 ms at line 18851 and several 130 to 214 ms entries inside DM-request-associated action IDs or uncorrelated snapshot work.

YAML stores observed:

| Line | Time | Duration | Parent action | Notes |
|---|---|---:|---|---|
| 26424 | 17:50:26.997Z | 100.594 ms | `perform_action` | Character persistence on action mutation. |
| 33718 | 17:54:23.317Z | 946.301 ms | `lay_on_hands_use` | Worst YAML write. |
| 38408 | 17:55:34.287Z | 809.716 ms | `wild_shape_apply` | Subcost inside 12.989 second action. |
| 42634 | 17:57:07.229Z | 927.012 ms | `perform_action` | Slow write on action mutation. |
| 45836 | 17:58:54.674Z | 482.581 ms | `cast_spell`, `hellish-rebuke` | Persistence write during cast. |
| 45992 | 17:59:04.500Z | 474.497 ms | `spell_target_request`, `hellish-rebuke` | Persistence write during target flow. |
| 53399 | 18:02:56.469Z | 96.931 ms | `attack_request` | Character persistence on attack path. |

Conclusions:

- YAML cache cold load is a startup blocker and an incidental background contributor.
- YAML write spans can add visible delay to specific interactive actions.
- The primary 8 to 13 second gameplay hang remains the forced snapshot rebuild because many worst actions have no large YAML write and still hang.
- No player YAML write in this trace can be attributed to `manual_override` or `long_rest` because those flows are absent.

## Spell, Reaction, AoE, And Summon Analysis

### Slowest spell actions

Slow spell casts are not limited to complex spells:

| Spell | Root `cast_spell` duration | Action ID | Dominant child |
|---|---:|---|---|
| `shield` | 13,831.611 ms | `action-929448efba6a4769a65a647538063321` | Forced state snapshot rebuild, 11,176.985 ms `lan.snapshot.build`. |
| `toll-the-dead` | 11,919.202 ms | `action-fe34e65255d7407c9607e3a0b8e9beb9` | Forced state snapshot rebuild, 11,745.226 ms. |
| `mage-armor` | 11,441.589 ms | `action-bc20bfaf00314ffc803d2e582419d0de` | Forced state snapshot rebuild, 9,122.737 ms. |
| `fire-bolt` | 11,416.570 ms | `action-61ce49d033d54548bc668b6e5c6d8a6d` | Forced state snapshot rebuild, 11,307.739 ms. |
| `blindness-deafness` | 10,899.312 ms | `action-ea0e1a368cd843b9b0d0d6b41f7fa71c` | Forced state snapshot rebuild, 8,539.396 ms. |

### Reactions

- Hellish Rebuke is slow on cast: 9,727.144 ms root dispatch. Its child state rebuild dominates, and it also writes YAML for 482.581 ms.
- Shield is the single slowest observed cast: 13,831.611 ms. Its follow-up rejected target requests add 3,129.338 and 2,820.532 ms.
- A single `player_command.create_reaction_offer.dispatch` span exists at 0.374 ms under the Hellish Rebuke target flow.
- Console log at 12:59:03 says a `counterspell` reaction offer was skipped because there were no websocket targets.
- `pending_reaction_count` is zero for all observed rows. There are no explicit reaction response/resolve commands in the websocket dispatch summary. This trace cannot prove expiration/clear correctness for a real pending prompt.

### AoE

- AoE target resolution is not expensive in the trace. `_map_spell_effect_targets` ran six times at 0.440 ms average and 1.021 ms worst.
- AoE target resolution is broken for six observed attempts. Child spans are `ok:false`, reason `AttributeError`; console says the handler raised `'NoneType' object has no attribute 'normalized'`.
- The failing AoE attempts include `shatter`, `fireball`, two `lightning-bolt` attempts, and `wall-of-fire`. The `cast_aoe` root dispatches still finish `ok:true` in about 42 to 71 ms, so callers can see a fast action that did not actually resolve correctly.

### Summons

- `echo_summon` at 8,712.731 ms and `dismiss_summons` at 8,565.839 ms are slow because they run the same forced snapshot refresh path.
- `summon-construct` casts at 19:00:18Z and 19:00:25Z are only about 14 ms each.
- `create-undead` cast at 19:03:22Z is 14.807 ms.
- This trace supports one expensive summon-control refresh path and several cheap summon spell cast entries. It does not prove authoritative summon placement success.

## Movement And Dijkstra Analysis

No span or command containing `dijkstra` appears in the required grep or span summaries.

Observed movement costs:

| Span | Count | Average | Worst | Relationship |
|---|---:|---:|---:|---|
| `_lan_shortest_cost` | 11 | 40.484 ms | 90.504 ms | Child of `move` actions. |
| `_lan_try_move` | 11 | 41.199 ms | 91.490 ms | Child of `move` actions. |

The movement spans are tied to explicit `move` actions, not redraw or broad snapshot churn in the current trace. The trace does not support movement optimization as the first pass.

## Error Analysis

### Trace errors and negative outcomes

| Error class | Count | Evidence | Impact |
|---|---:|---|---|
| Startup LAN snapshot `TypeError` | 1 in live trace, 1 in each startup trace with full startup rows | Live trace lines 7-8; startup traces line 7-8 | Snapshot path can fail during cold start before the later slow empty snapshot. |
| `dm.broadcast.snapshot` `TypeError` | 47 | Live trace `broadcast.end` rows such as lines 6422, 8921, 95600 | DM broadcast side fails on many mutation refreshes while LAN broadcast reports success. |
| Attack `KeyError` | 1 failed action span stack | Trace lines 29683-29689; console traceback at 12:52:31 CDT | `attack_request` fails on missing `weapon_name`. |
| AoE mapping `AttributeError` | 6 `_map_spell_effect_targets` and 6 `_handle_cast_aoe_request` child spans | Lines 137258-137262, 142270-142274, 149184-149189, 154568-154572, 155273-155277, 161611-161615 | AoE resolution correctness failure. |
| Spell target request `REJECTED` result status | 36 result rows | Target request summary and target action table | Valid instrumentation result, but some rejection paths are slow. |

### Console failures

- The live console has a full traceback at 2026-05-21 12:52:31 CDT for `KeyError: 'weapon_name'` in the attack request path.
- The live console has repeated `cast_aoe handler raised: 'NoneType' object has no attribute 'normalized'` warnings at 13:46:11, 13:49:18, 13:53:33, 13:56:54, 13:57:20, and 14:01:12 CDT.
- The live console warns at 12:59:03 CDT that one counterspell offer was skipped because there were no websocket targets.

### Sends, broadcasts, JSONL, and analyzer limits

- Completed LAN broadcasts show `failed_send_count:0`.
- Completed LAN broadcasts show one recipient. No evidence supports fanout-to-many-clients as the current blocker.
- Failed DM broadcast rows do not emit `failed_send_count` or duration; they emit `ok:false` and `reason:"TypeError"`.
- The analyzer reported zero malformed or non-object JSONL lines for all analyzed candidate traces.
- `scripts/analyze_debug_trace.py` is useful for summaries but does not reconstruct a parent/child span tree, does not compute exclusive time, and sums nested spans for action totals. It also does not emit line references or grouped error tables. This report used root websocket dispatch rows and explicit child-span grouping to avoid double-counting.

## Suspected Root Causes Ranked By Evidence

| Rank | Candidate | Evidence grade | Finding |
|---|---|---|---|
| 1 | Redundant or too-expensive forced snapshot rebuilds | High | Shared across slow spell, facing, summon, dismiss, and wild-shape actions. `lan.snapshot.build` is 4.535 seconds average and cache-miss every time. |
| 2 | Background LAN snapshot churn | High | `_lan_snapshot` count is 32,993 with many slow threshold hits and mostly missing action IDs. It is likely competing with interactive work or exposing the same expensive construction path. |
| 3 | Frontend polling implied by backend traffic | Medium-high | 511 DM combat polls and very frequent LAN snapshot work are visible. Backend trace does not prove repaint cost, but it proves traffic/work cadence. |
| 4 | Rejected spell target validation waits | Medium-high | Multiple no-broadcast `spell_target_request` rejections take 2 to 3 seconds. This is especially visible after slow Shield and Blindness/Deafness casts. |
| 5 | YAML/cache writes and repeated cache touches | Medium | Cold load is severe and writes add 0.48 to 0.95 seconds on specific actions. Repeated cache touches show up under snapshots, but they do not explain every multi-second action. |
| 6 | Broadcast payload send cost | Medium-low | Repeated 1.2 MB static payload sends cost 71 to 107 ms. State send duration tracks payload size, but one-recipient send cost is far below snapshot build time. |
| 7 | Startup-only load | High for startup, low for gameplay root cause | Cold `_load_player_yaml_cache` and empty first snapshot are reproducible startup suspects, not enough to explain later gameplay hangs. |
| 8 | Map/spell target resolution | Low for latency, high for AoE correctness | AoE mapping is very cheap before it fails. |
| 9 | Movement/Dijkstra | Low | No Dijkstra rows; explicit movement cost is below 100 ms. |

## Optimization Plan

No optimization is authorized in this task. The phased plan below is the evidence-backed next sequence.

### Phase 1: Quick Wins, Low Risk

| Item | Exact suspected code area | Expected latency improvement | Risk | Validation | Tests to add/run | Rollback plan |
|---|---|---|---|---|---|---|
| Stop cheap mutation refreshes from forcing a cold full LAN state rebuild when an equivalent fresh snapshot is already available | `_lan_force_state_broadcast` and the callers used by player cast/facing/summon mutation refreshes; state snapshot cache contract around `lan.snapshot.build` | High for the 8 to 13 second hang family if cache miss/full rebuild is avoided | Medium | Repeat live debug trace for `cast_spell`, `set_facing`, `echo_summon`, and `dismiss_summons`; compare root dispatch and `lan.snapshot.build` counts/durations | Focused player command and LAN broadcast/snapshot cache tests; `py_compile` edited Python | Revert the bounded refresh/cache change; keep instrumentation and tests that do not alter behavior |
| Stop static data rebroadcast on refreshes that only mutate combat state | `_lan_force_state_broadcast(include_static/hydrate_static)` caller policy and LAN broadcast payload selection | 70 to 107 ms per affected refresh plus less browser traffic | Low-medium | In trace, static payload count and 1.2 MB send rows should drop for state-only actions without missing spell/static UI data | Tests that state-only mutation still updates client while static data remains available after connect | Restore prior include-static policy for the specific caller family |
| Add targeted instrumentation if the root build still has hidden exclusive time | Snapshot build internals around LAN state snapshot hydrating profiles, spell static data, and map projections | Diagnostic, not direct latency | Low | New trace must break `lan.snapshot.build` into actionable child costs | Instrumentation tests only if existing debug utility has coverage | Remove extra debug spans if too noisy |

### Phase 2: Backend Hot Path Fixes

| Item | Exact suspected code area | Expected latency improvement | Risk | Validation | Tests to add/run | Rollback plan |
|---|---|---|---|---|---|---|
| Reduce background `_lan_snapshot` work cadence or work content when state is unchanged | LAN controller tick/poll snapshot path around `_lan_snapshot` | High background CPU/work reduction; interactive impact likely if contention is real | Medium-high | Trace should show far fewer `_lan_snapshot` completions and slow threshold rows while client remains connected | Tests for reconnect/state freshness and snapshot invalidation; live trace with idle client and active combat | Restore prior cadence/content flags behind a narrow switch |
| Avoid repeated player YAML cache touch inside one snapshot/action pass | `_load_player_yaml_cache` usage reached through LAN snapshot/player profile hydration and existing cache hold pattern | Low to medium for gameplay; high for background count | Medium | Per-action `_load_player_yaml_cache` count should drop from 40 to 81 on worst actions; cache correctness stays stable | Cache hold/revalidation tests and focused spell/action snapshot tests | Revert hold scope expansion |
| Move or coalesce safe character YAML writes after immediate result delivery if durability contract allows | `_store_character_yaml` call sites observed in spell target, wild shape, lay on hands, perform action | Up to about 0.5 to 0.95 seconds on affected actions | Medium-high due persistence safety | Trace persistence ordering and saved-data correctness under simulated failure | Persistence safety tests; warning-clean focused action tests | Restore synchronous write behavior |
| Repair DM broadcast snapshot `TypeError` before relying on DM/LAN dual refresh | DM snapshot broadcast helper producing `dm.broadcast.snapshot` `TypeError` | Correctness and diagnosis clarity; latency secondary | Medium | Zero failed DM broadcast snapshot rows on mutation smoke | Focused DM snapshot/broadcast tests | Revert bounded DM broadcast fix |

### Phase 3: Frontend, Render, And Poll Fixes If Evidence Continues

| Item | Exact suspected code area | Expected latency improvement | Risk | Validation | Tests to add/run | Rollback plan |
|---|---|---|---|---|---|---|
| Revisit DM polling interval and duplicate refresh triggers | `/dm` and `/dmcontrol` client fetch cadence implied by 511 `GET /api/dm/combat` requests | Medium DM load reduction if backend polls are causing contention | Medium | Compare DM poll count and DM snapshot durations with identical live smoke | Browser syntax check if HTML assets change; focused backend route tests | Restore prior polling cadence |
| Reconcile LAN repaint behavior after backend sends less static/full state | LAN client receive/render path for state/static payloads | Browser responsiveness improvement if repaint is still slow after backend fix | Medium | Browser smoke and trace should show less traffic for same result semantics | Browser syntax check and targeted UI smoke | Restore prior render path for state payload handling |

Phase 3 is gated. The backend trace proves request/snapshot traffic, not a frontend paint bottleneck by itself.

### Phase 4: Deeper Architecture And Cache Changes

| Item | Exact suspected code area | Expected latency improvement | Risk | Validation | Tests to add/run | Rollback plan |
|---|---|---|---|---|---|---|
| Split canonical mutation result from heavyweight hydrated client snapshot assembly | Player command result/broadcast orchestration and LAN/DM snapshot contracts | Large if it replaces state-wide rebuilds for narrow mutations | High | Mutations return fast explicit result and broadcast minimal deltas while reconnect still rebuilds canonical state | Contract tests, reconnect tests, focused live trace | Keep compatibility full-state fallback until delta path is proven |
| Formalize snapshot invalidation/cache ownership per LAN and DM consumer | Snapshot cache keys, invalidation events, static-data ownership | Large sustained work reduction | High | Cache-hit/miss trace is explainable; stale-state regression suite remains clean | Cache invalidation and hidden-information tests | Disable new cache path and return to full snapshot rebuild |

## Next Gemini/Codex Implementation Task

Use this bounded prompt for the highest-confidence optimization pass:

```text
Read first:
- docs/runtime_reports/spell_engine_latency_forensics_20260521_1430.md
- docs/runtime_reports/spell_engine_latency_debugging_runbook_20260521_1213.md
- docs/dm_spell_engine_living_plan.md
- .agent/rules/00-init-tracker-core.md
- .agent/rules/20-agent-safety-and-scope.md

Task:
Implement one bounded backend optimization for the live action latency family proven by the 2026-05-21 trace. Reduce or eliminate the multi-second forced LAN state rebuild on state-only player actions without broad refactor.

Behavior change:
- For state-only LAN player mutation refreshes demonstrated by slow `cast_spell`, `set_facing`, `echo_summon`, and `dismiss_summons`, avoid rebuilding/rebroadcasting heavyweight static state when a current combat-state snapshot path is sufficient.
- Preserve backend authority, reconnect correctness, hidden-information handling, result semantics, and saved-data behavior.
- Keep full snapshot/static-data behavior for initial connect/reconnect or any path that cannot prove state-only safety.
- Do not change spell resolution rules or AoE geometry in this pass.

Allowed files:
- dnd_initative_tracker.py only if the refresh/cache ownership call site is still there
- player_command_service.py only if a narrow refresh caller change is required
- tests/ for focused coverage
- docs/runtime_reports/ for the required implementation report
- majorTODO.md only if the pass changes tracker status

Do not touch:
- assets/web/dm/index.html
- assets/web/lan/index.html
- combat_service.py
- runtime_config.py
- map/tactical layer files
- YAML/data files
- deployment files

Validation:
- python3 -m py_compile on every edited Python file
- warning-clean focused unittest coverage for the edited LAN refresh/cache path and player commands
- run a focused trace smoke if available for one state-only spell cast and one cheap non-spell state mutation
- report root dispatch time, `_lan_force_state_broadcast` count, `lan.snapshot.build` count, `lan.snapshot.build` cache-hit/miss evidence, static-data broadcast count, and any regressions

Required report:
- docs/runtime_reports/spell_engine_latency_optimization_pass_YYYYMMDD_HHMM.md
- Include before/after trace evidence and exactly which state refresh paths changed.

Stop conditions:
- A safe change requires broad cache architecture redesign.
- Hidden-information, reconnect, claims/auth, or persistence safety becomes uncertain.
- The pass needs frontend asset changes or AoE correctness work.
- Tests pass only with warnings or unrelated failures are obscured.

No broad refactor. No per-spell special case. Do not deploy or push.
```

## Appendix A: Analyzer Output Summary

Analyzer summary for the live trace:

- Events: 197,711
- Input lines: 197,711
- Ignored bad lines: 0
- Total trace duration: 6,284,501 ms
- Total action IDs: 883
- Websocket dispatch count: 220
- Root websocket action families by total dispatch time include `cast_spell` 29 calls at 4,624.818 ms average, `set_facing` 7 calls at 8,701.929 ms average, `spell_target_request` 44 calls at 711.736 ms average, and `wild_shape_apply` 1 call at 12,988.962 ms.
- Broadcast summary: `lan.broadcast.state` is only 47 sends at 13.299 ms average; `lan.broadcast.payload static_data` is 23 sends at 82.596 ms average.
- Snapshot summary: `_lan_snapshot` 32,993 calls, `lan.snapshot.build` 49 calls, `_dm_console_snapshot_payload` 578 calls, `_dm_tactical_snapshot` 531 calls.
- YAML/cache summary: `_load_player_yaml_cache` 58,269 calls, `_store_character_yaml` 7 calls.

Analyzer summary for startup probes:

- `debug-trace-20260521-123205.jsonl`: 26 events, no action IDs, cold YAML and empty LAN snapshot/broadcast spike.
- `debug-trace-20260521-123501.jsonl`: 569 events, no action IDs, same startup spike plus repeated empty snapshot polling.
- `debug-trace-20260521-123300.jsonl`: one event only.

## Appendix B: Top 30 Slow Span Ends

| Rank | Line | Timestamp | Duration | Span | Command | Action ID |
|---|---:|---|---:|---|---|---|
| 1 | 95574 | 18:20:57.698Z | 13,831.160 ms | `ws.action.dispatch` | `cast_spell` | `action-929448efba6a4769a65a647538063321` |
| 2 | 95572 | 18:20:57.698Z | 13,830.609 ms | `player_command.cast_spell` | `cast_spell` | `action-929448efba6a4769a65a647538063321` |
| 3 | 95570 | 18:20:57.697Z | 13,830.024 ms | `_handle_cast_spell_request` | `cast_spell` | `action-929448efba6a4769a65a647538063321` |
| 4 | 39163 | 17:55:46.383Z | 12,988.630 ms | `ws.action.dispatch` | `wild_shape_apply` | `action-806fb8b451e04ebf984ea1fb0f51a119` |
| 5 | 90390 | 18:18:07.958Z | 11,918.890 ms | `ws.action.dispatch` | `cast_spell` | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 6 | 90388 | 18:18:07.958Z | 11,918.576 ms | `player_command.cast_spell` | `cast_spell` | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 7 | 90386 | 18:18:07.958Z | 11,918.154 ms | `_handle_cast_spell_request` | `cast_spell` | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 8 | 90384 | 18:18:07.958Z | 11,903.442 ms | `_lan_force_state_broadcast` | none | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 9 | 39789 | 17:55:58.344Z | 11,762.942 ms | `_lan_snapshot` | none | none |
| 10 | 39161 | 17:55:46.382Z | 11,752.162 ms | `_lan_force_state_broadcast` | none | `action-806fb8b451e04ebf984ea1fb0f51a119` |
| 11 | 90302 | 18:18:07.800Z | 11,745.226 ms | `lan.snapshot.build` | `state` | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 12 | 90300 | 18:18:07.799Z | 11,744.899 ms | `_lan_snapshot` | none | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 13 | 39079 | 17:55:46.264Z | 11,633.054 ms | `lan.snapshot.build` | `state` | `action-806fb8b451e04ebf984ea1fb0f51a119` |
| 14 | 39077 | 17:55:46.263Z | 11,632.633 ms | `_lan_snapshot` | none | `action-806fb8b451e04ebf984ea1fb0f51a119` |
| 15 | 92233 | 18:19:14.277Z | 11,441.173 ms | `ws.action.dispatch` | `cast_spell` | `action-bc20bfaf00314ffc803d2e582419d0de` |
| 16 | 92231 | 18:19:14.277Z | 11,440.839 ms | `player_command.cast_spell` | `cast_spell` | `action-bc20bfaf00314ffc803d2e582419d0de` |
| 17 | 92229 | 18:19:14.276Z | 11,440.440 ms | `_handle_cast_spell_request` | `cast_spell` | `action-bc20bfaf00314ffc803d2e582419d0de` |
| 18 | 79376 | 18:13:46.037Z | 11,416.090 ms | `ws.action.dispatch` | `cast_spell` | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 19 | 79374 | 18:13:46.037Z | 11,415.704 ms | `player_command.cast_spell` | `cast_spell` | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 20 | 79372 | 18:13:46.036Z | 11,415.168 ms | `_handle_cast_spell_request` | `cast_spell` | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 21 | 79370 | 18:13:46.036Z | 11,401.088 ms | `_lan_force_state_broadcast` | none | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 22 | 79290 | 18:13:45.943Z | 11,307.739 ms | `lan.snapshot.build` | `state` | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 23 | 79288 | 18:13:45.942Z | 11,307.270 ms | `_lan_snapshot` | none | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 24 | 95568 | 18:20:57.697Z | 11,268.401 ms | `_lan_force_state_broadcast` | none | `action-929448efba6a4769a65a647538063321` |
| 25 | 95488 | 18:20:57.606Z | 11,176.985 ms | `lan.snapshot.build` | `state` | `action-929448efba6a4769a65a647538063321` |
| 26 | 95486 | 18:20:57.605Z | 11,176.456 ms | `_lan_snapshot` | none | `action-929448efba6a4769a65a647538063321` |
| 27 | 96382 | 18:21:15.417Z | 11,096.149 ms | `_lan_snapshot` | none | none |
| 28 | 99163 | 18:22:28.829Z | 10,898.943 ms | `ws.action.dispatch` | `cast_spell` | `action-ea0e1a368cd843b9b0d0d6b41f7fa71c` |
| 29 | 99161 | 18:22:28.829Z | 10,898.611 ms | `player_command.cast_spell` | `cast_spell` | `action-ea0e1a368cd843b9b0d0d6b41f7fa71c` |
| 30 | 99159 | 18:22:28.829Z | 10,898.211 ms | `_handle_cast_spell_request` | `cast_spell` | `action-ea0e1a368cd843b9b0d0d6b41f7fa71c` |

## Appendix C: Top 30 Slow Root Websocket Actions

| Rank | Line | Timestamp | Duration | Command | Result | OK | Action ID |
|---|---:|---|---:|---|---|---|---|
| 1 | 95576 | 18:20:57.698Z | 13,831.611 ms | `cast_spell` | none | true | `action-929448efba6a4769a65a647538063321` |
| 2 | 39165 | 17:55:46.383Z | 12,988.962 ms | `wild_shape_apply` | none | true | `action-806fb8b451e04ebf984ea1fb0f51a119` |
| 3 | 90392 | 18:18:07.959Z | 11,919.202 ms | `cast_spell` | none | true | `action-fe34e65255d7407c9607e3a0b8e9beb9` |
| 4 | 92235 | 18:19:14.277Z | 11,441.589 ms | `cast_spell` | none | true | `action-bc20bfaf00314ffc803d2e582419d0de` |
| 5 | 79378 | 18:13:46.037Z | 11,416.570 ms | `cast_spell` | none | true | `action-61ce49d033d54548bc668b6e5c6d8a6d` |
| 6 | 99165 | 18:22:28.829Z | 10,899.312 ms | `cast_spell` | none | true | `action-ea0e1a368cd843b9b0d0d6b41f7fa71c` |
| 7 | 100446 | 18:23:32.734Z | 10,798.616 ms | `cast_spell` | none | true | `action-fbd1709f8ee6469a91dc6d79fbb6f3c1` |
| 8 | 69870 | 18:11:10.582Z | 9,754.748 ms | `cast_spell` | none | true | `action-de0d2ec4b32447dfaf27da8efa83ba39` |
| 9 | 45945 | 17:59:03.449Z | 9,727.144 ms | `cast_spell` | none | true | `action-bf98e11b21cd4a649975e79c0cae1365` |
| 10 | 161572 | 19:01:12.799Z | 8,996.203 ms | `set_facing` | none | true | `action-7c8708b953054342874edcc23fec802b` |
| 11 | 86024 | 18:16:57.285Z | 8,992.261 ms | `cast_spell` | none | true | `action-11ac0e87f18e4e36b83104246a821886` |
| 12 | 142231 | 18:49:18.020Z | 8,956.825 ms | `set_facing` | none | true | `action-0c2cb7f7302c4666aecbffa692295d37` |
| 13 | 137219 | 18:46:11.845Z | 8,884.913 ms | `set_facing` | none | true | `action-1356b192bda848b685c2989c3490caf7` |
| 14 | 82685 | 18:14:48.849Z | 8,856.442 ms | `cast_spell` | none | true | `action-3dd936d116df4aa3b5aa1abf97fe798b` |
| 15 | 65246 | 18:08:22.527Z | 8,757.119 ms | `cast_spell` | none | true | `action-cf3d4c4dacea4edabfc20f905d5c5fbc` |
| 16 | 64664 | 18:08:00.997Z | 8,720.904 ms | `cast_spell` | none | true | `action-985f140eadac48498080a7668a481875` |
| 17 | 26749 | 17:50:49.752Z | 8,712.731 ms | `echo_summon` | none | true | `action-db2447fb4d89498c9a39511be3ef4f1e` |
| 18 | 84484 | 18:15:57.501Z | 8,699.971 ms | `cast_spell` | none | true | `action-2cdb20a53437472db93ff445b9f7bdac` |
| 19 | 149146 | 18:53:33.334Z | 8,613.464 ms | `set_facing` | none | true | `action-7a1c0f7e8b644a559c6fb21862ec3bac` |
| 20 | 154529 | 18:56:54.105Z | 8,570.502 ms | `set_facing` | none | true | `action-a9627ffbf33d469686f1fd9ef813ef54` |
| 21 | 27016 | 17:51:03.613Z | 8,565.839 ms | `dismiss_summons` | none | true | `action-9ec1f920e5e34857b1eb5b7635d9fcc9` |
| 22 | 155234 | 18:57:20.398Z | 8,453.529 ms | `set_facing` | none | true | `action-ad94d812335f4c5e8ec55647687e4f03` |
| 23 | 151407 | 18:54:58.912Z | 8,438.066 ms | `set_facing` | none | true | `action-eccf5ff3652446078791a13749dfbe7f` |
| 24 | 95701 | 18:21:00.828Z | 3,129.338 ms | `spell_target_request` | `REJECTED` | true | `action-4f34c5d5bf6c4234a06c724aa8677cc1` |
| 25 | 95890 | 18:21:03.649Z | 2,820.532 ms | `spell_target_request` | `REJECTED` | true | `action-88fa439842e84111bab7755ff006ac3c` |
| 26 | 99285 | 18:22:37.715Z | 2,292.230 ms | `spell_target_request` | `REJECTED` | true | `action-4f1a695930e04513b86e5f40047a0286` |
| 27 | 92257 | 18:19:16.489Z | 2,212.197 ms | `spell_target_request` | `REJECTED` | true | `action-0f03c099080a4ed8a8921904eadf7804` |
| 28 | 99225 | 18:22:31.053Z | 2,202.072 ms | `spell_target_request` | `REJECTED` | true | `action-cfef1b6b717b484d876069d4c18ccc3a` |
| 29 | 99239 | 18:22:33.242Z | 2,188.906 ms | `spell_target_request` | `REJECTED` | true | `action-c11003b483fa4b7a85425ab50d1937b0` |
| 30 | 99253 | 18:22:35.423Z | 2,180.621 ms | `spell_target_request` | `REJECTED` | true | `action-2aebee701f5846dea619541caca7df74` |

## Appendix D: Top 30 Repeated Expensive Spans

The trace only has 27 distinct completed timed span names, so this table lists all span names sorted by total inclusive duration.

| Rank | Span | Count | Total inclusive duration | Average | Worst |
|---|---|---:|---:|---:|---:|
| 1 | `_lan_snapshot` | 32,993 | 1,988,181.613 ms | 60.261 ms | 11,762.942 ms |
| 2 | `ws.action.dispatch` | 220 | 264,748.686 ms | 1,203.403 ms | 13,831.160 ms |
| 3 | `_lan_force_state_broadcast` | 49 | 225,545.446 ms | 4,602.968 ms | 11,903.442 ms |
| 4 | `lan.snapshot.build` | 49 | 222,217.089 ms | 4,535.043 ms | 11,745.226 ms |
| 5 | `player_command.cast_spell` | 29 | 134,097.279 ms | 4,624.044 ms | 13,830.609 ms |
| 6 | `_handle_cast_spell_request` | 29 | 134,082.547 ms | 4,623.536 ms | 13,830.024 ms |
| 7 | `http.request` | 663 | 114,376.379 ms | 172.513 ms | 2,735.201 ms |
| 8 | `_dm_console_snapshot_payload` | 578 | 103,134.066 ms | 178.433 ms | 1,644.105 ms |
| 9 | `_dm_tactical_snapshot` | 531 | 90,052.648 ms | 169.591 ms | 1,601.343 ms |
| 10 | `_load_player_yaml_cache` | 58,269 | 59,034.321 ms | 1.013 ms | 9,836.800 ms |
| 11 | `player_command.spell_target_request` | 44 | 31,267.526 ms | 710.626 ms | 3,128.210 ms |
| 12 | `combat_service.combat_snapshot` | 601 | 12,707.806 ms | 21.144 ms | 259.649 ms |
| 13 | `_store_character_yaml` | 7 | 3,837.632 ms | 548.233 ms | 946.301 ms |
| 14 | `player_command.attack_request` | 11 | 2,234.817 ms | 203.165 ms | 361.758 ms |
| 15 | `_adjudicate_attack_request` | 11 | 2,224.132 ms | 202.194 ms | 360.814 ms |
| 16 | `dm.console.snapshot.build` | 47 | 1,666.548 ms | 35.458 ms | 91.127 ms |
| 17 | `player_command.end_turn` | 15 | 1,151.998 ms | 76.800 ms | 331.043 ms |
| 18 | `lan.broadcast.payload` | 101 | 977.900 ms | 9.682 ms | 55.790 ms |
| 19 | `lan.broadcast.state` | 47 | 592.308 ms | 12.602 ms | 49.281 ms |
| 20 | `_lan_try_move` | 11 | 453.192 ms | 41.199 ms | 91.490 ms |
| 21 | `_lan_shortest_cost` | 11 | 445.321 ms | 40.484 ms | 90.504 ms |
| 22 | `player_command.cast_aoe` | 7 | 321.689 ms | 45.956 ms | 70.782 ms |
| 23 | `_handle_cast_aoe_request` | 7 | 317.806 ms | 45.401 ms | 70.270 ms |
| 24 | `player_command.reset_turn` | 35 | 12.832 ms | 0.367 ms | 0.626 ms |
| 25 | `_map_spell_effect_targets` | 6 | 2.643 ms | 0.440 ms | 1.021 ms |
| 26 | `combat_service.apply_damage` | 11 | 1.463 ms | 0.133 ms | 0.159 ms |
| 27 | `player_command.create_reaction_offer.dispatch` | 1 | 0.374 ms | 0.374 ms | 0.374 ms |

## Appendix E: Assumptions And Missing Instrumentation

Assumptions:

- Trace timestamps are UTC and console timestamps are America/Chicago as emitted.
- Root websocket dispatch duration is the best available user-action wall time for LAN actions.
- Missing `action_id` means action correlation is unavailable; no attempt was made to invent ownership for uncorrelated background `_lan_snapshot` rows.
- Console warnings are included as correctness evidence even when the JSONL root dispatch reports `ok:true`.

Missing instrumentation that would tighten the next pass:

- Child spans inside the seconds-long `lan.snapshot.build` path with exclusive timing for static hydration, player profile hydration, spell preset/static serialization, map payload assembly, and any cache lock/wait.
- A reason/status payload on `cast_aoe` root dispatch when a child handler fails, so `ok:true` does not hide a failed result.
- Duration and error detail for `dm.broadcast.snapshot` failed broadcast rows.
- Explicit frontend poll source or page tag for background `_lan_snapshot` triggers, to separate websocket tick, reconnect hydration, and HTTP/poll sources.
- Correlation from reaction offer creation through pending prompt delivery, response, expiry, and clear; this trace never reaches a pending reaction count above zero.

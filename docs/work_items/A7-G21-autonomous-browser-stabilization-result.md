# A7-G21 Autonomous Browser Stabilization Result

Date: `2026-07-16`

Task ID: `CODEX-20260716-a7-autonomous-browser-stabilization-g21`

Work item: `WORK-20260715-a7-browser-automation`

Gate: `A7-G21`

Starting commit: `2de96537b1ad156e5bf8dbab2fe04447df6d0e56`

Terminal classification: `controlled-stop-application-defect`

Browser result: `fail`

## Result

G21 reconstructed and retained all evidence-validated G17 harness corrections,
added the three accepted G12/G13 regressions and twelve focused G17
regressions, and passed the exact accumulated 35-node focused validation. One
changed-code browser attempt then ran against the accepted G19 synchronization
correction. It advanced through the first four live actors and stopped at
Fred's player action after proving that backend authority had advanced to Fred
while Fred's already-connected claimed surface remained on the initial active
actor and kept its End Turn control disabled.

This is application-owned behavior outside the two allowed harness/test files.
No application file was edited, no harness workaround was added, and unchanged
code was not retried. All independently validated G21 harness and regression
progress is retained.

The approximately-200-enemy stress scenario was not executed.

## Accepted Harness Corrections Retained

- exactly one normal click on `#closeToolboxBtn` followed by exactly one normal
  click on `#startCombatBtn`;
- a successful `POST /api/dm/combat/start` response barrier;
- live combat-authoritative action ordering, including verified Owl/Raven
  summon turns;
- visible-canvas geometry for browser-accessible mapped coordinates;
- interaction only with `#turnModal.show`;
- live active-actor capability synchronization;
- keyword `arg=` use for Playwright `wait_for_function` calls;
- nearest mapped enemy selection;
- visible current spellbook controls and real targeted spell selection;
- noncaster attack fallback;
- normal melee token drag staging;
- enabled-player-turn transition barriers;
- immediate successful-save spell results without requiring a resolution
  modal;
- DM-control active-CID transition barriers; and
- summon active-CID transition barriers.

No force click, DOM-bypass click, JavaScript click, hit-testing bypass, or
presentation-order assumption was introduced.

## Focused Validation

The required compile command exited `0` in less than `0.1 seconds`:

```text
timeout 30s .venv/bin/python3 -m py_compile \
  scripts/validation/browser-smoke-harness.py \
  tests/test_browser_smoke_harness.py
```

The exact accumulated focused command exited `0`; `35 passed in 1.78s`
(`2.01 seconds` command wall time):

```text
timeout 120s .venv/bin/python3 -m pytest -q \
  tests/test_browser_smoke_harness.py::TestBrowserSmokeHarness::test_help \
  tests/test_browser_smoke_harness.py::TestBrowserSmokeHarness::test_list_scenarios \
  tests/test_browser_smoke_harness.py::TestBrowserSmokeHarness::test_list_exploration_scenario \
  tests/test_browser_smoke_harness.py::TestBrowserSmokeHarness::test_multi_round_cli_args \
  tests/test_browser_smoke_harness.py::TestBrowserSmokeHarness::test_unknown_scenario \
  tests/test_browser_smoke_harness.py::test_three_surface_plan_uses_verified_selectors_and_ordered_steps \
  tests/test_browser_smoke_harness.py::test_three_surface_roster_setup_precedes_encounter_tab \
  tests/test_browser_smoke_harness.py::test_three_surface_plan_requires_versioned_fixture_contract \
  tests/test_browser_smoke_harness.py::test_three_surface_contract_mismatch_is_terminal_without_retry \
  tests/test_browser_smoke_harness.py::test_three_surface_evidence_schema_records_required_artifacts_and_timings \
  tests/test_browser_smoke_harness.py::test_three_surface_cleanup_refuses_unverified_process_ownership \
  tests/test_browser_smoke_harness.py::test_three_surface_scenario_executes_registered_executor \
  tests/test_browser_smoke_harness.py::test_three_surface_executor_runs_ordered_plan_once \
  tests/test_browser_smoke_harness.py::test_three_surface_corrected_setup_steps_execute_once \
  tests/test_browser_smoke_harness.py::test_three_surface_enemy_options_accept_reordered_complete_set \
  tests/test_browser_smoke_harness.py::test_three_surface_enemy_options_reject_missing_slug \
  tests/test_browser_smoke_harness.py::test_three_surface_enemy_options_reject_extra_slug \
  tests/test_browser_smoke_harness.py::test_three_surface_enemy_options_reject_duplicate_slug \
  tests/test_browser_smoke_harness.py::test_three_surface_executor_failure_records_terminal_evidence \
  tests/test_browser_smoke_harness.py::test_three_surface_executor_never_retries_after_failure \
  tests/test_browser_smoke_harness.py::test_three_surface_start_combat_closes_toolbox_before_single_start_click \
  tests/test_browser_smoke_harness.py::test_three_surface_start_combat_uses_normal_clicks_without_force_or_dom_bypass \
  tests/test_browser_smoke_harness.py::test_three_surface_start_combat_waits_for_successful_response_before_returning \
  tests/test_browser_smoke_harness.py::test_three_surface_runtime_actions_follow_live_authoritative_order \
  tests/test_browser_smoke_harness.py::test_three_surface_mapped_positions_use_visible_canvas_geometry \
  tests/test_browser_smoke_harness.py::test_three_surface_turn_alert_interacts_only_with_visible_modal \
  tests/test_browser_smoke_harness.py::test_three_surface_active_capabilities_use_keyword_wait_argument \
  tests/test_browser_smoke_harness.py::test_three_surface_target_selection_uses_nearest_in_range_enemy \
  tests/test_browser_smoke_harness.py::test_three_surface_spell_plan_uses_visible_current_controls \
  tests/test_browser_smoke_harness.py::test_three_surface_noncaster_spell_step_falls_back_to_attack \
  tests/test_browser_smoke_harness.py::test_three_surface_melee_attacks_drag_to_staging_position \
  tests/test_browser_smoke_harness.py::test_three_surface_player_action_waits_for_enabled_turn \
  tests/test_browser_smoke_harness.py::test_three_surface_successful_spell_save_is_immediate_result \
  tests/test_browser_smoke_harness.py::test_three_surface_enemy_action_waits_for_dmcontrol_active_cid \
  tests/test_browser_smoke_harness.py::test_three_surface_summon_advance_waits_for_active_transition
```

The required candidate check exited `0` in less than `0.1 seconds`:

```text
timeout 10s git diff --check -- \
  scripts/validation/browser-smoke-harness.py \
  tests/test_browser_smoke_harness.py
```

No full test file, broad suite, collection-only command, discovery substitute,
or unbounded test command ran.

## Browser Attempt

Exactly one changed-code attempt ran with the required command and exited `1`:

```text
.venv/bin/python3 scripts/validation/browser-smoke-harness.py --scenario black-tan-three-surface-workflow --base-url http://localhost:8787 --artifact-root logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g21_browser-artifacts
```

Attempt `20260716_210626` passed reset, all roster/enemy additions, combat
start, runtime verification, all ten player claims, Suppression Gunner's DM
action/advance, Vicnor's staged attack/End Turn, Captain's DM action/advance,
and Throat Goat's Eldritch Blast/End Turn. It failed at ordered step 50,
`player-attack-pc:fred`, after the `#endTurn:not([disabled])` barrier remained
unsatisfied for `10.043 seconds`.

## Proven Application Defect

Throat Goat's normal End Turn click completed. The debug trace records command
`end_turn`, player/cid `9`, action
`5fe91614-78d3-489d-a3ac-43e79b7e4d65`, receipt and queueing at
`2026-07-17T02:06:56.815Z`, dispatch at `02:06:56.887Z`, a forced LAN snapshot
at combat version `15`, and command completion with `ok:true` at
`02:06:57.028Z`. The relevant trace records are lines `11249` through `11518`.

The exact post-failure request was `GET /api/dm/combat`. The preserved HTTP
response was `200 OK` with action ID
`action-57b8472303ba4ae49360c3b21f42aa32`, `in_combat:true`,
`active_cid:4`, `turn:5`, `round:1`, no pending prompts, and authoritative turn
order:

```text
[21, 10, 13, 9, 4, 18, 2, 3, 14, 15, 17, 20, 6, 8, 16, 19, 7, 5, 1, 11, 12]
```

Fred is claimed as `cid=4`. Fred's preserved role trace snapshot after
`call@303` still marks Suppression Gunner `cid=21` active and records
`#endTurn` with `disabled` and title `Wait for your turn, matey.`. The bounded
wait is `call@625`. The terminal screenshot shows the same visible state.

This separates a successful player command and authoritative backend advance
from a stale already-connected claimed player surface. Reload, reconnect,
reclaim, polling, or manual interaction would be a forbidden workaround.

## Evidence

- Artifact run:
  `logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g21_browser-artifacts/black-tan-three-surface-workflow/20260716_210626/`
- Summary: `summary.json` and `summary.md`
- Screenshot: `terminal-selector-failure-player-attack-pc:fred.png`
- Fred trace: `role-trace-player-pc-fred.zip`
- All-role traces: the remaining `browser-trace.zip` and `role-trace-*.zip`
  files in the artifact run
- Exact post-failure response: `post-failure-dm-combat.headers` and
  `post-failure-dm-combat.json`
- Server log:
  `logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g21_smoke-server_20260716-210456.log`
- Debug trace: `logs/debug-trace-20260716-210456.jsonl`

## Server Ownership and Cleanup

Before startup, `ss` returned no port 8787 listener and `lsof` returned no
matching process. G21 started exactly one server with the packet command.

Before browser execution and again before cleanup, the same-user owned
processes were shell `88315`, Python `88316`, and tee `88317`, all in process
group/session `88315`, all with cwd
`/home/a2-jeeves@iamjeeves.dev/src/init-tracker`. Python's argv used
`.venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787`; its executable
inode matched `.venv/bin/python`, and `INIT_TRACKER_DEBUGGING=1` was present.
Both `ss` and `lsof` attributed the 8787 listener to Python PID `88316`.

The verified process group received SIGINT through its controlling terminal.
The server exited `130`; shell, Python, and tee were reaped. Final bounded
checks found no listed PID or PGID `88315` member, and both `ss` and `lsof`
proved port 8787 free. SIGKILL was not used and no unverified process was
adopted or stopped.

## Human Gate

The developer/orchestrator must inspect and authorize another bounded
application correction. The minimum known application/test family remains:

- `assets/web/lan/index.html` for connected-player state application and turn
  control enablement;
- `dnd_initative_tracker.py` for authoritative LAN snapshot/broadcast version
  delivery; and
- `tests/test_server_runtime.py` for the connected-player transition,
  version-ordering, personalized claim, and command-broadcast regressions.

The correction must prove that every claimed connected surface, including a
surface that is neither the immediately prior nor next actor until several
turns later, applies the latest backend-authoritative actor without reload,
reconnect, reclaim, polling, or manual interaction. No further harness,
browser, runtime, network, push, deployment, restart, scheduler, production,
or service action is authorized by this result.

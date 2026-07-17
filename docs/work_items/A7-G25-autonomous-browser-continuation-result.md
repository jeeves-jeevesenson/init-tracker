# A7-G25 Autonomous Browser Continuation Result

Date: `2026-07-16`

Task ID: `CODEX-20260716-a7-autonomous-browser-continuation-g25`

Work item: `WORK-20260715-a7-browser-automation`

Gate: `A7-G25`

Starting commit: `009449ef0ef7228e630cfdc40ef2e5c884bff31e`

Terminal classification: `controlled-stop-application-defect`

Browser result: `fail`

## Result

G25 ran two changed-code browser attempts from the retained G21 harness and
accepted G23 fanout correction. The first attempt proved one harness defect.
That defect was corrected with one focused regression and the accumulated
explicit 36-node validation passed. The second attempt then proved that
backend turn authority skipped a living Raven summon that remained in the
authoritative turn order. That behavior is application-owned and outside the
two allowed harness/test files.

No application file was edited, no application workaround was added, and
unchanged code was not retried. The validated G25 harness correction and its
focused regression are retained. The approximately-200-enemy stress scenario
was not executed.

## Browser Attempts

### Attempt 1: `20260716_230627`

The exact browser command exited `1`:

```text
.venv/bin/python3 scripts/validation/browser-smoke-harness.py --scenario black-tan-three-surface-workflow --base-url http://localhost:8787 --artifact-root logs/smoke/CODEX-20260716-a7-autonomous-browser-continuation-g25_browser-artifacts
```

Attempt 1 passed 54 ordered steps and failed at step 55,
`advance-player-turn-pc:eldramar`, after `30072.072 ms`. Eldramar's Fire Bolt
opened the ordinary `#attackResolveModal.show` interaction, but
`_finish_targeted_spell()` checked only `#spellResolveModal.show` and accepted
the launch-only note `Casted Fire Bolt.` as a completed result. The following
normal End Turn click was intercepted by the still-open attack-resolution
modal for 30 seconds.

The terminal screenshot shows the visible `Resolve Attack` modal. The Eldramar
role trace records `#spellResolveModal.show` as not visible, the exact launch
note, the visible `#attackResolveModal`, and repeated ordinary-click
interception. Its preserved document snapshot identifies the real confirm
control as `#attackResolveSubmit`.

### Retained G25 Harness Correction

`_finish_targeted_spell()` now:

- resolves visible spell-attack interactions through the ordinary
  `#attackResolveSubmit` button;
- continues to resolve visible spell-save/AoE interactions through the
  existing `#spellResolveSubmit` path;
- does not treat `Casted <spell>.` as a terminal result; and
- retains the existing immediate result behavior for result notes beginning
  with `<spell>:` such as a successful saving throw.

The focused regression
`test_three_surface_spell_attack_waits_for_attack_resolution_modal` reproduces
the exact launch note before the delayed attack-resolution modal becomes
visible. It proves the harness waits one poll and normally clicks
`#attackResolveSubmit`.

No force click, DOM-bypass click, JavaScript click, or hit-testing bypass was
introduced.

### Attempt 2: `20260716_231013`

The same exact browser command ran against the validated changed code and
exited `1`. Attempt 2 passed 47 ordered steps and failed at step 48,
`advance-summon-turn-raven-33`, after `10013.209 ms` waiting for DM-control to
render Raven `cid=33` as the active actor.

The initial authoritative runtime order was:

```text
[38, 26, 32, 33, 34, 27, 35, 40, 29, 30, 28, 37, 25, 42, 36, 41, 22, 39, 23, 24, 31]
```

The relevant identities were Stikhiya `cid=32`, Raven `cid=33`, and Black and
Tan Captain `cid=34`. The terminal screenshot renders Captain active on
DM-control rather than Raven.

## Proven Application Defect

Stikhiya's normal End Turn interaction emitted exactly one command:

- action ID `1676c006-d23b-4eed-babb-cd703657e9b3`;
- trace ID `tr-a3358c47-d5c7-4057-9c99-636ff3f50109`;
- received at `2026-07-17T04:10:41.836Z`;
- queued at `04:10:41.837Z`;
- dispatched at `04:10:42.009Z` for player/cid `32`;
- forced snapshot built at combat version `33`;
- scheduled fanout to ten connected player recipients;
- command completed with `ok:true` at `04:10:42.267Z`; and
- broadcast completed with ten sends and zero failures at `04:10:42.446Z`.

The relevant debug trace begins at line `34682`. No duplicate End Turn command
or DM-control next-turn command followed it.

After the failed browser barrier, the exact preserved request was
`GET /api/dm/combat`. It completed in `0.032061 seconds` and returned `200 OK`
with:

- action ID `action-c33428240aba4efbbba75768601a3120`;
- trace ID `trace-5ba9421770944674818aa0c07d813ba0`;
- `in_combat:true`;
- round `1`, turn `4`;
- `active_cid:34` (Black and Tan Captain);
- `up_next_cid:27` (Johnny Morris);
- the unchanged authoritative turn order containing Raven `cid=33`
  immediately before Captain `cid=34`;
- Raven still present at 2/2 HP, without conditions, and marked as a summoned
  ally; and
- no pending prompts.

The backend battle log ends this transition with:

```text
END R1 стихия
START R1 Black and Tan Captain 1
```

It contains no Raven start/end entry. This proves that backend authority, not
only the DM-control presentation, skipped the living summon. Reload,
reconnect, order rewriting, or a harness-side second advance would be an
unauthorized workaround.

## Focused Validation

Before Attempt 1, the required compile command exited `0` in less than
`0.1 seconds`:

```text
timeout 30s .venv/bin/python3 -m py_compile \
  scripts/validation/browser-smoke-harness.py \
  tests/test_browser_smoke_harness.py
```

The exact retained list exited `0`; `35 passed in 1.68s` (`1.91 seconds`
command wall time). After the G25 correction, the same compile command exited
`0`, and the accumulated exact command below exited `0`; `36 passed in 1.80s`
(`2.03 seconds` command wall time):

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
  tests/test_browser_smoke_harness.py::test_three_surface_summon_advance_waits_for_active_transition \
  tests/test_browser_smoke_harness.py::test_three_surface_spell_attack_waits_for_attack_resolution_modal
```

Before each attempt, the corresponding accumulated explicit focused list and
the required two-file check passed. After the candidate correction, the exact
check was:

```text
timeout 10s git diff --check -- \
  scripts/validation/browser-smoke-harness.py \
  tests/test_browser_smoke_harness.py
```

It exited `0` in less than `0.1 seconds`. No full test file, broad suite,
collection-only command, keyword selection, wildcard selection, stress
scenario, or unbounded test command ran.

## Evidence

- Attempt 1 artifact run:
  `logs/smoke/CODEX-20260716-a7-autonomous-browser-continuation-g25_browser-artifacts/black-tan-three-surface-workflow/20260716_230627/`
- Attempt 1 summary: `summary.json` and `summary.md`
- Attempt 1 screenshot:
  `terminal-selector-failure-advance-player-turn-pc:eldramar.png`
- Attempt 1 Eldramar trace: `role-trace-player-pc-eldramar.zip`
- Attempt 2 artifact run:
  `logs/smoke/CODEX-20260716-a7-autonomous-browser-continuation-g25_browser-artifacts/black-tan-three-surface-workflow/20260716_231013/`
- Attempt 2 summary: `summary.json` and `summary.md`
- Attempt 2 screenshot:
  `terminal-visible-state-inconsistency-advance-summon-turn-raven-33.png`
- Attempt 2 DM-control trace: `role-trace-dmcontrol.zip`
- Exact post-failure response: `post-failure-dm-combat.headers` and
  `post-failure-dm-combat.json` in the Attempt 2 artifact run
- Server log:
  `logs/smoke/CODEX-20260716-a7-autonomous-browser-continuation-g25_smoke-server_20260716-230518.log`
- Debug trace: `logs/debug-trace-20260716-230518.jsonl`

Each artifact run also retains the DM/browser trace and all ten player role
traces. The one bounded final evidence-path `stat` command exited `0` and
confirmed the exact server-log and debug-trace paths above.

## Server Ownership and Cleanup

Before startup, `ss` returned no port 8787 listener and `lsof` returned no
matching process. G25 started exactly one server with the required packet
command.

Before both browser attempts and again before cleanup, the same-user owned
processes were shell `99055`, Python `99056`, and tee `99057`, all in process
group/session `99055`, all with cwd
`/home/a2-jeeves@iamjeeves.dev/src/init-tracker`. Python's argv was
`.venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787`; its executable
inode matched `.venv/bin/python`; and `INIT_TRACKER_DEBUGGING=1` plus the
repository `PWD` were present. Both `ss` and `lsof` attributed the 8787
listener to Python PID `99056`.

The verified process group received SIGINT through its controlling terminal.
The server session exited `130`. Shell, Python, and tee were reaped; no PID or
PGID `99055` member remained; and both `ss` and `lsof` proved port 8787 free.
SIGKILL was not used and no unverified process was adopted or stopped.

## Changed Tracked Files

- `scripts/validation/browser-smoke-harness.py`
- `tests/test_browser_smoke_harness.py`
- `docs/work_items/current_work.md`
- `docs/work_items/WORK-20260715-a7-browser-automation.md`
- `docs/work_items/A7-G25-autonomous-browser-continuation-result.md`

## Terminal State

```text
A7_GATE=A7-G25
A7_STATE=autonomous-browser-continuation-controlled-stop
A7_G25_STATE=controlled-stop
A7_G25_RESULT=docs/work_items/A7-G25-autonomous-browser-continuation-result.md
A7_IMPLEMENTATION_AUTHORIZED=false
A7_TEST_EXECUTION_AUTHORIZED=false
A7_BROWSER_EXECUTION_AUTHORIZED=false
A7_RUNTIME_EXECUTION_AUTHORIZED=false
A7_NETWORK_AUTHORIZED=false
A7_PUSH_AUTHORIZED=false
A7_DEPLOYMENT_AUTHORIZED=false
A7_RESTART_AUTHORIZED=false
A7_SCHEDULER_AUTHORIZED=false
A7_PRODUCTION_AUTHORIZED=false
A7_SERVICE_MUTATION_AUTHORIZED=false
```

## Human Gate

The developer/orchestrator must inspect and authorize a bounded application
turn-advancement correction and focused server-runtime regression. The future
scope must prove that a living, condition-free Owl or Raven summon present in
the authoritative `turn_order` becomes active exactly once between its
adjacent canonical actors, and that both backend and connected surfaces agree
without a harness-side extra advance. Exact application filenames must be
named by that later task packet after bounded application-owner inspection.

No further harness, browser, runtime, network, push, deployment, restart,
scheduler, production, or service action is authorized by this result.

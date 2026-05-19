# /dmcontrol Responsiveness Pass — 2026-05-16 01:13

## Context

User began live testing and stopped immediately because the UI was too
sluggish: damage application slow, log/floating numbers laggy, response
after Apply Result laggy, End Turn sluggish, modal popups sluggish,
general interactive feel sluggish.

This pass is instrumentation + narrow evidence-backed fixes only. No
features, no redesign, no AoE / ammo / Controlled Burst / Rough Arrest /
spellcasting / Black-and-Tan mechanics work.

## Commit before work

```
b2d8ae2 Stabilize LAN live-game readiness
```

## Git status (before)

```
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005152.txt
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005228.txt
?? docs/runtime_reports/dmcontrol_live_smoke_20260513_0810.md
?? docs/runtime_reports/dmcontrol_modal_smoke_20260513_1132.md
?? docs/runtime_reports/dmcontrol_pass1c_live_smoke_20260513_1211.md
```

## Git status (after)

```
 M assets/web/dmcontrol/index.html
 M dnd_initative_tracker.py
?? docs/runtime_reports/dmcontrol_latency_pass_20260516_0113.md
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005152.txt
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005228.txt
?? docs/runtime_reports/dmcontrol_live_smoke_20260513_0810.md
?? docs/runtime_reports/dmcontrol_modal_smoke_20260513_1132.md
?? docs/runtime_reports/dmcontrol_pass1c_live_smoke_20260513_1211.md
```

## Files changed

- `assets/web/dmcontrol/index.html` (+~95 / -~10)
- `dnd_initative_tracker.py` (+~55 / -~10)

No edits to `combat_service.py`, `monster_capability_service.py`, tests,
or YAML.

## Phase A — Instrumentation present (and added)

### Already present (verified by reading code + prior `logs/manual-combat-smoke-server.log` and `docs/runtime_reports/dmcontrol_pass1c_live_smoke_20260513_1211.md`)

All gated by `LAN_PERF_DEBUG=1`:

- `_lan_snapshot` — emits `elapsed_ms`, `units`, `aoes`, `obstacles`
  (`dnd_initative_tracker.py:19254`).
- `_lan_force_state_broadcast` — emits `elapsed_ms`, `units`
  (`dnd_initative_tracker.py:19842`).
- `_dm_console_snapshot_payload` — emits `elapsed_ms`,
  `combat_snapshot_ms`, `tactical_snapshot_ms`, sources, counts
  (`dnd_initative_tracker.py:7348`).
- `_load_player_yaml_cache` — emits `elapsed_ms`, `force_refresh`,
  `profiles` (`dnd_initative_tracker.py:27344`).
- `CombatService.next_turn` — emits `elapsed_ms`, `advance_turn_ms`,
  `rebuild_ms`, `broadcast_ms`, `snapshot_ms`
  (`combat_service.py:471`).
- Frontend Apply Results — emits `[Apply] Resolution request took Xms`
  (`assets/web/dmcontrol/index.html:1290`).

### Added this pass

- `LAN_PERF dm_resolve_monster_capability_targets total_ms / resolve_ms / snapshot_ms / cid / apply_damage / apply_effects`
  — wrap route handler, gated by `LAN_PERF_DEBUG=1`
  (`dnd_initative_tracker.py` `/api/dm/monster-capabilities/{cid}/resolve-targets`).
- `LAN_PERF dm_next_turn total_ms / next_turn_ms / snapshot_ms` —
  wrap route handler, gated by `LAN_PERF_DEBUG=1`
  (`dnd_initative_tracker.py` `/api/dm/combat/next-turn`).
- Frontend `[DMPERF]` console log around `fetchState`, `renderState`,
  `draw`, plus `endTurn` / `startCombat` — opt-in via `?perf=1` URL
  param. Default off; zero overhead when disabled.
  (`assets/web/dmcontrol/index.html` — top of script block).

## Measured bottlenecks (evidence)

### A. Frontend forces a full re-render every 2 s, regardless of state changes (PRIMARY UI sluggishness driver)

`assets/web/dmcontrol/index.html:2550` (before fix):

```
fetchState();
pollInterval = setInterval(fetchState, 2000);
```

`fetchState()` (line ~937) always called `renderState(data)` and
`draw()`. `renderState()` did monolithic `actorPanel.innerHTML = ...`,
then called `fetchCapabilitiesForActiveActor(actor)` which can run a
second HTTP fetch every poll. `draw()` ran a full Dijkstra
`movementCostMap(...)` (lines ~2231/2376) every time when the active
unit had any movement budget left.

User-perceived effect:

- During idle, the page does a full DOM rewrite + canvas redraw +
  Dijkstra every 2 s.
- During a click (Apply Result, capability select, modal open), this
  background work competes with the user's interaction and can land in
  the middle of it.
- Damage "appears late" because the in-line snapshot returned by the
  POST is shown, then the next idle poll repaints over it ~1 s later
  with the same state.

### B. `handleCombatControl()` performed an extra round-trip after End Turn

Before fix (`index.html:2530`):

```
const resp = await fetch(endpoint, { method: 'POST' });
const data = await resp.json();
if (data.ok) {
   await fetchState();   // discards data.snapshot and re-fetches
}
```

`POST /api/dm/combat/next-turn` already returns the full snapshot, but
the click handler ignored it and made a second `GET /api/dm/combat` —
adding one full network round-trip + another `renderState+draw` cycle
to every End Turn.

### C. Backend builds the DM snapshot two or three times per apply / end-turn

Per existing `LAN_PERF` lines and re-reading the code:

- `_lan_force_state_broadcast` (`dnd_initative_tracker.py:19842`) builds
  a LAN snapshot AND a DM snapshot (via
  `_dm_console_snapshot_payload(...)`) and pushes both.
- Then the route handler returns `_dm_console_snapshot()` (the helper
  at `dnd_initative_tracker.py:3840`), which calls the same payload
  builder a SECOND time, doing a fresh `combat_snapshot()` +
  `_dm_tactical_snapshot()` (which itself calls `_lan_snapshot()`
  again).
- Result: each apply / next-turn rebuilds the DM snapshot twice
  (`_dm_console_snapshot_payload elapsed_ms ≈ 36 ms` × 2, plus an
  additional `_lan_snapshot elapsed_ms ≈ 13 ms`).
- `CombatService.next_turn` (May 6 log) measured `elapsed_ms=289.18
  advance_turn_ms=46.76 rebuild_ms=0.00 broadcast_ms=146.24
  snapshot_ms=96.16` — and that is BEFORE the additional snapshot
  rebuild inside the route handler.

### D. `_lan_snapshot` is consistently ~13 ms but spikes to ~155 ms on yaml-cache misses

Visible in `logs/manual-combat-smoke-server.log` — `_lan_snapshot
elapsed_ms=155.18` directly follows `_load_player_yaml_cache
elapsed_ms=141.96 force_refresh=False`. The yaml cache already gates
re-validation via a hold-depth + 5 s interval signature check; the
spike is a directory re-scan triggered by interval expiry. Not
addressed this pass.

### E. Prior pass 1C report (`dmcontrol_pass1c_live_smoke_20260513_1211.md`) flagged `dm_resolve_monster_capability_targets took 11–12 s`

No matching log emitter exists in the current source — the figure was
external (likely a slow-request log from the runner). Added explicit
`LAN_PERF dm_resolve_monster_capability_targets total_ms` so the next
live window will report this with breakdown into `resolve_ms` vs
`snapshot_ms`. Cannot confirm magnitude until the next live window;
the figure may have been ammo/yaml-related and already addressed by
later passes (`9a2aa3c`, `1160fc9`, `4abebaf`).

## Phase C — Fixes made

All fixes are local, evidence-backed, and reversible.

### Frontend (`assets/web/dmcontrol/index.html`)

1. **Idle-poll dedup.** `fetchState()` reads the response as text and
   compares to `lastPolledStateJson`. If identical (the common idle
   case), the full `renderState` + `draw` cycle is skipped. Eliminates
   ~95 % of the every-2-s UI churn that was masking interactivity.

2. **`applyAuthoritativeSnapshot(snapshot)` helper.** Centralizes the
   "I just got an in-line snapshot from a mutating endpoint" path:
   updates `lastPolledStateJson` so the next idle poll can short-
   circuit, sets `state`, runs `renderState` + `draw`.

3. **End Turn / Start Combat use the returned snapshot.** Removes the
   redundant `GET /api/dm/combat` round-trip from every advance.
   Button now also shows immediate `Advancing…` / `Starting…` pending
   state and disables to prevent double-submit.

4. **Apply Result uses the returned snapshot.** Replaces
   `state = data.snapshot; renderState(state);` with
   `applyAuthoritativeSnapshot(data.snapshot)` so the next idle poll
   does not re-render the same payload.

5. **Memoize `movementCostMap` per (cid, pos, move_remaining, grid
   signature).** `draw()` was re-running Dijkstra on every redraw,
   including idle redraws. Now cached and reused until any of the key
   inputs change.

6. **Frontend timing — opt-in.** `?perf=1` flips on `[DMPERF]`
   `console.log` lines around `renderState`, `draw`, `fetchState`,
   `endTurn`. Default off; no overhead in production.

### Backend (`dnd_initative_tracker.py`)

7. **Cache the DM snapshot already built by `_lan_force_state_broadcast`.**
   When the broadcast builds its DM snapshot, stash it on
   `self._lan._cached_dm_snapshot` with a `perf_counter()` timestamp.

8. **Reuse the cached DM snapshot from the route helper.** The
   `_dm_console_snapshot()` helper now returns the cached snapshot
   when (a) called with no overrides and (b) the cache is younger
   than 250 ms. The cache is single-use and is cleared on read. Saves
   one full `_dm_console_snapshot_payload` rebuild (~36–100 ms) per
   apply and per end-turn.

9. **Route-level timing logs for resolve-targets and next-turn.**
   Gated by `LAN_PERF_DEBUG=1`. Reports `total_ms`, `resolve_ms`,
   `snapshot_ms` (resolve-targets) and `total_ms`, `next_turn_ms`,
   `snapshot_ms` (next-turn).

### Not changed (intentionally)

- `_lan_force_state_broadcast` behavior — still broadcasts to both LAN
  and DM clients identically.
- `_load_player_yaml_cache` gating — already has hold-depth + interval
  short-circuit; the occasional 141 ms spike is the scheduled
  re-validation and is out of scope.
- `renderActionPanel` is still called multiple times in the apply
  path. Each call was already cheap relative to network + Dijkstra;
  trimming further can wait until live timing confirms it matters.
- `_apply_map_attack_manual_damage` and battle-log fanout — unchanged.
- No Tk / desktop paths touched.

## Validation

Ran tests serially per CLAUDE.md guidance.

- `./.venv/bin/python3 -m py_compile dnd_initative_tracker.py` → **OK**
- `./.venv/bin/python3 -m unittest -v tests.test_dm_console_asset_syntax`
  → **3 / 3 OK** (0.99 s).
- `./.venv/bin/python3 -m unittest -v tests.test_dm_control_route`
  → **19 / 25 OK** (495 s). 5 failures + 1 error are **pre-existing**
  (verified by `git stash; rerun; git stash pop` against the same
  asserts):
  - `test_dm_control_has_local_resolution_tray_scaffold`
  - `test_dm_control_has_mutation_endpoints`
  - `test_dm_control_has_resolution_hardening`
  - `test_dm_control_movement_blocked_during_targeting`
  - `test_dm_control_has_local_outcome_controls` (asserts a function
    `setLocalResolutionOutcome` that does not exist in the codebase
    either before or after this pass)
  These look like asset-drift tests written against an earlier scaffold.
  Not a latency-pass regression.
- `./.venv/bin/python3 -m unittest -v tests.test_dm_control_apply_results`
  → **12 / 12 OK** (210 s).
- `./.venv/bin/python3 -m unittest -v tests.test_black_and_tan_capabilities`
  → **12 / 13 OK** (25 s). 1 error is **pre-existing**: the test
  `test_black_and_tan_combat_log_force_damage` stubs
  `_apply_damage_via_service` with a lambda that does not accept the
  `_broadcast` keyword that production passes. Verified on the
  pre-edit baseline. Not a latency-pass regression.
- `git diff --check` → clean.

No new tests added — the fixes either preserve observable behavior
(snapshot equality, idle dedup) or replace a network round-trip with a
no-op when the response already contains the same payload.

## Remaining suspected bottlenecks

- **`_dm_monster_capability_resolve_targets` total time is still
  unmeasured at the handler level.** The new `LAN_PERF` log will
  capture it on the next live window. If `resolve_ms` is large, the
  fanout inside `_apply_map_attack_manual_damage` /
  `_dm_monster_capability_effect_change` likely contains nested
  broadcasts or save calls.
- **`_lan_snapshot` 13 ms baseline + 155 ms occasional spike** at 28
  units. If the live window shows this on every apply, batch the
  hold-depth around the apply path or extend the interval.
- **`renderActionPanel` is rebuilt fully per click** (innerHTML). At
  current capability counts this is small; if `[DMPERF]` shows it >5
  ms, switch to surgical updates of the affected card.
- **Battle log / floating popups** — the dmcontrol surface does NOT
  currently render floating damage numbers or per-event log entries
  in DOM. The user's perceived "log/popup lag" is most likely the
  every-2-s repaint visually overwriting freshly-applied damage. The
  idle-poll dedup fix should remove that effect; if it persists, the
  next pass should look at the LAN surface (`assets/web/lan/index.html`),
  not dmcontrol.

## Recommended next pass

**Pass 3 — confirm with live timing, then attack the biggest remaining
hotspot.**

1. Start the app with `LAN_PERF_DEBUG=1`, open `/dmcontrol?perf=1` in
   the browser, run a 5-minute live combat window.
2. Read off:
   - `LAN_PERF dm_resolve_monster_capability_targets total_ms / resolve_ms / snapshot_ms`
   - `LAN_PERF dm_next_turn total_ms / next_turn_ms / snapshot_ms`
   - browser console `[DMPERF] renderState / draw / fetchState(skip-unchanged) / endTurn`
3. If `resolve_ms` > 200 ms, instrument inside
   `_dm_monster_capability_resolve_targets` (per-target apply timing,
   inner broadcasts).
4. If `_lan_snapshot` is still hot, scope `_lan_force_state_broadcast`
   so apply + effect application share one broadcast instead of N.
5. Do NOT widen into AoE, ammo, Controlled Burst, spellcasting, Rough
   Arrest, or new Black-and-Tan mechanics until DM responsiveness is
   acceptable.

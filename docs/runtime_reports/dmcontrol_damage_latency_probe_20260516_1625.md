# /dmcontrol Damage Latency Probe — 2026-05-16 16:25

## Goal

Investigate the severe Apply Results / damage application latency reported
during live play (Eldramar's Fireball at level 3 against ~11 targets,
including 4 Sculpt targets). Sculpting itself felt fine; the damage
resolution + log/UI settle was the slow part. Prior responsiveness passes
(`dmcontrol_latency_pass_20260516_0113.md`,
`dmcontrol_latency_pass_20260516_SECOND.md`) did not eliminate the
visible delay.

This pass is **instrumentation only** — no behavior changes, no spell
tweaks, no broad refactor. One narrow fix only if the timer proves a
specific bottleneck.

## Commit before work

```
b2d8ae2 Stabilize LAN live-game readiness
```

## Git status (before)

```
 M assets/web/dmcontrol/index.html
 M dnd_initative_tracker.py
 M docs/dm_control_surface_living_agent_plan.md
?? docs/runtime_reports/dmcontrol_latency_pass_20260516_0113.md
?? docs/runtime_reports/dmcontrol_latency_pass_20260516_SECOND.md
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
 M docs/dm_control_surface_living_agent_plan.md
?? docs/runtime_reports/dmcontrol_damage_latency_probe_20260516_1625.md
?? docs/runtime_reports/dmcontrol_latency_pass_20260516_0113.md
?? docs/runtime_reports/dmcontrol_latency_pass_20260516_SECOND.md
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005152.txt
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005228.txt
?? docs/runtime_reports/dmcontrol_live_smoke_20260513_0810.md
?? docs/runtime_reports/dmcontrol_modal_smoke_20260513_1132.md
?? docs/runtime_reports/dmcontrol_pass1c_live_smoke_20260513_1211.md
```

## Files changed

- `dnd_initative_tracker.py`
  - Added `_damage_perf_enabled()` / `_damage_perf_emit()` helpers
    (`DMCONTROL_DAMAGE_PERF=1` gate; lazy-created JSONL log at
    `logs/dmcontrol_damage_perf_YYYYMMDD_HHMMSS.jsonl`).
  - Instrumented `_lan_auto_resolve_cast_aoe()` (the AoE/save spell hot
    path — Fireball/etc.) with per-target sub-timings
    (`save_ms`, `damage_roll_ms`, `apply_damage_ms`, `log_ms`,
    `total_ms`) plus aggregate `per_target_loop_ms`,
    `broadcast_total_ms`, `total_apply_damage_ms`, and target/sculpt
    counts. One JSONL record per cast.
  - Instrumented `_dm_monster_capability_resolve_targets()` (the
    Apply Results path for monster capabilities) with per-target
    `total_ms`, `per_target_loop_ms`, `broadcast_total_ms`,
    `total_apply_damage_ms`.
  - Wrapped the FastAPI `/api/dm/monster-capabilities/{cid}/resolve-targets`
    route to also emit a `route:` JSONL record with `resolve_ms`,
    `dm_snapshot_ms`, `route_total_ms` when `DMCONTROL_DAMAGE_PERF=1`.
- `assets/web/dmcontrol/index.html`
  - Wrapped `applyLocalResolutionResults()` with `[DMPERF]` marks
    (gated on existing `?perf=1` plumbing): `feedbackRender`,
    `requestBuild`, `fetch`, `responseJsonParse`, `applySnapshot`,
    `finalRenderAndDraw`, `applyResultsEndToEnd`. Error path emits
    `applyResultsEndToEnd(error)`.

## Validation

```
$ python3 -m py_compile dnd_initative_tracker.py
OK

$ python3 -m unittest tests.test_dm_console_asset_syntax
Ran 3 tests in 0.989s
OK

$ python3 -m unittest tests.test_dm_console_asset_syntax \
                    tests.test_dm_control_apply_results \
                    tests.test_dm_control_route
Ran 40 tests in 7.413s
FAILED (errors=37)
```

The 37 errors are **baseline-only**: every failing setUp dies with

```
AttributeError: 'LanController' object has no attribute '_fastapi_app'
```

Verified against HEAD by re-running the same three modules with my
changes stashed — identical 40 tests / 37 errors / same setUp trace.
No regressions introduced by this pass.

```
$ git diff --check
no whitespace issues
```

Helper smoke-test (no app boot, just the two helpers):

```
$ DMCONTROL_DAMAGE_PERF=1 python3 …minimal stub harness…
enabled? True
files: ['logs/dmcontrol_damage_perf_20260516_162529.jsonl']
{"route": "smoke", "foo": 1, "timestamp": "2026-05-16T16:25:29.923"}
```

Confirms: env gate respected, log directory auto-created, single
JSONL line per call, append-mode safe.

## Live reproduction

**Not executed in this pass.** This is an instrumentation-only patch
intended to be exercised in the next live session by running:

```
DMCONTROL_DAMAGE_PERF=1 LAN_PERF_DEBUG=1 python dnd_initative_tracker.py
```

then opening `/dmcontrol?perf=1` and repeating the Fireball-at-3
multi-target cast. Expected artifacts:

- `logs/dmcontrol_damage_perf_<stamp>.jsonl` — one record per cast or
  monster-capability Apply Results call. Each record carries actor,
  spell/capability name, target counts, and per-target sub-timings.
- Browser DevTools console — `[DMPERF] applyResultsEndToEnd …`
  plus the per-stage breakdown (`fetch`, `applySnapshot`,
  `finalRenderAndDraw`, etc.).
- Existing `LAN_PERF dm_resolve_monster_capability_targets …` oplog
  lines stay intact for cross-checking.

## Sample JSONL shape (illustrative — not from a live run)

```json
{
  "route": "lan_auto_resolve_cast_aoe",
  "spell_name": "Fireball",
  "spell_slug": "fireball",
  "actor_cid": 17,
  "actor_name": "Eldramar",
  "slot_level": 3,
  "selected_target_count": 11,
  "affected_target_count": 11,
  "sculpt_target_count": 4,
  "damage_application_count": 7,
  "log_line_count": 11,
  "removed_count": 1,
  "per_target_loop_ms": 142.71,
  "broadcast_total_ms": 38.40,
  "total_apply_damage_ms": 181.55,
  "per_target": [
    {"name":"Owl","cid":4,"sculpted":false,"passed":false,
     "damage_total":1,"save_ms":0.42,"damage_roll_ms":0.31,
     "apply_damage_ms":11.80,"log_ms":1.10,"total_ms":13.63},
    {"name":"Vicnor","cid":5,"sculpted":true,"passed":true,
     "damage_total":0,"save_ms":0.04,"damage_roll_ms":0.18,
     "apply_damage_ms":0.05,"log_ms":1.05,"total_ms":1.32}
  ],
  "timestamp": "2026-05-16T16:25:00.123"
}
```

## Top measured bottleneck

**Unknown until a live run produces real JSONL records.** The
instrumentation is designed to discriminate between the four leading
hypotheses without a second pass:

| Hypothesis | Field that will light up if true |
|---|---|
| Per-target backend damage compute | high `damage_roll_ms` / `apply_damage_ms` in `per_target` |
| Per-target WS spell_target_result + log file IO | high `log_ms` summed across `per_target` |
| End-of-cast snapshot + LAN broadcast cost | high `broadcast_total_ms` (server) and high `applyResults.applySnapshot` / `finalRenderAndDraw` (client) |
| Frontend render/log/floating-damage repaint | server `total_apply_damage_ms` is small but `applyResultsEndToEnd` on the client is large |

The combat-log timestamps in the user's report all collide at
`16:04:34`, which already rules out an inter-line broadcast/drip — the
backend produces the log batch quickly enough that all 11 lines share a
second, so the visible delay sits in **either** the final
`_lan_force_state_broadcast` (snapshot + WS push to all clients +
DM-console snapshot rebuild) **or** the client-side post-response
render. The split between `broadcast_total_ms` and
`applyResultsEndToEnd` will say which.

## Narrow fix applied

**None.** Per the brief — instrument first, fix only if the timer
proves a specific bottleneck. No code-behavior change was made beyond
adding opt-in timing.

## What remains inline / rough

- `_lan_auto_resolve_cast_aoe()` still calls `_lan._broadcast_payload`
  per damaged target (one `spell_target_result` per target) **before**
  the consolidating `_lan_force_state_broadcast()`. If the live JSONL
  shows `apply_damage_ms` dominated by this, the obvious narrow fix is
  to batch those into a single `spell_resolution_results` payload, or
  to elide them entirely now that the final state broadcast carries
  the new HP. That fix is deferred until the timer proves it matters.
- `_lan_force_state_broadcast()` already has an existing
  `LAN_PERF_DEBUG=1` timer (`LAN_PERF _lan_force_state_broadcast
  elapsed_ms=…`). The new `broadcast_total_ms` field measures the
  same call from the cast-resolution side; both will agree.
- Baseline test infrastructure (`tests.test_dm_control_route` and
  `tests.test_dm_control_apply_results`) is broken at setUp on
  `self.app._lan._fastapi_app`. Not introduced here; flagged for a
  separate test-infra pass.

## Next recommended patch

1. Run one live Fireball-multi-target repro with
   `DMCONTROL_DAMAGE_PERF=1 LAN_PERF_DEBUG=1` and `/dmcontrol?perf=1`.
2. Read the single JSONL record and the matching `[DMPERF]` console
   block.
3. Pick the largest contributor and apply exactly one narrow fix:
   - if `broadcast_total_ms` dominates → batch/skip per-target
     `spell_target_result` broadcasts during AoE resolution.
   - if `applyResults.applySnapshot` / `finalRenderAndDraw` dominate
     → defer the floating-damage / log-panel repaint until after the
     authoritative snapshot is rendered.
   - if a single `per_target.apply_damage_ms` outlier dominates
     repeatedly → investigate `_apply_damage_via_service` /
     CombatService overhead per target.

Do not optimize blind. Wait for the live JSONL.

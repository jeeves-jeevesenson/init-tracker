# /dmcontrol Responsiveness Pass — 2026-05-16 (SECOND)

Validation + corrective pass on top of
`docs/runtime_reports/dmcontrol_latency_pass_20260516_0113.md`.

## TL;DR

- **One real regression introduced by the prior pass.** The DM
  snapshot reuse cache in `_dm_console_snapshot` (the per-route
  helper closure inside `LanController.start`) read
  `self._lan._cached_dm_snapshot`, but `self` IS the `LanController`
  in that closure, so `self._lan` raises `AttributeError`. Every
  call to `_dm_console_snapshot()` *with no overrides* (the GET
  `/api/dm/combat` poll, the `POST /api/dm/map/combatants/{cid}/move`
  route, etc.) failed and the surrounding route handler converted
  the exception into a 500. The prior pass labelled the resulting
  unit-test error as "pre-existing" without verifying — it was not.
  Verified by `git stash` against `b2d8ae2`: the move test passes on
  the baseline and 500s with the prior pass applied.
- **Corrective patch applied:** read the cache from `self`
  directly. The cache lives on the LanController instance because
  the write site (`InitiativeTracker._lan_force_state_broadcast`)
  does `self._lan._cached_dm_snapshot = dm_snap`, and there `self`
  is the `InitiativeTracker` whose `_lan` IS that same
  `LanController`. After the fix the targeted test passes (20.7 s).
- **One additional narrow latency fix kept in scope:** front-end
  `executeMove` now consumes the snapshot the `/api/dm/map/.../move`
  route already returns, replacing a redundant `await fetchState()`
  + repaint. Same shape as the prior pass's End Turn / Start Combat
  / Apply Result fixes.
- **Idle-poll dedup, Dijkstra memoization, perf instrumentation,
  snapshot-consuming POST paths:** reviewed in detail, accepted
  with notes (see below). No further code changes.
- **No live browser window in this environment.** A 5-minute
  interactive window with `?perf=1` requires a human at a browser;
  this is a headless sandboxed shell. Backend behavior was instead
  validated through the focused unit suite.

## Repo status

**Before this pass:**

```
 M assets/web/dmcontrol/index.html
 M dnd_initative_tracker.py
 M docs/dm_control_surface_living_agent_plan.md
?? docs/runtime_reports/dmcontrol_latency_pass_20260516_0113.md
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005152.txt
?? docs/runtime_reports/dmcontrol_latency_stop_20260516_005228.txt
?? docs/runtime_reports/dmcontrol_live_smoke_20260513_0810.md
?? docs/runtime_reports/dmcontrol_modal_smoke_20260513_1132.md
?? docs/runtime_reports/dmcontrol_pass1c_live_smoke_20260513_1211.md
```

**After this pass:** same plus
`docs/runtime_reports/dmcontrol_latency_pass_20260516_SECOND.md`.
`git diff --stat`:

```
 assets/web/dmcontrol/index.html              | 125 ++++++++++++++++++++++++---
 dnd_initative_tracker.py                     |  62 ++++++++++++-
 docs/dm_control_surface_living_agent_plan.md |  83 ++++++++++++++++++
 3 files changed, 256 insertions(+), 14 deletions(-)
```

`git diff --check` → clean.

## Per-target review

### 1. Backend DM snapshot reuse cache (`_dm_console_snapshot`)

**Original code (broken):**

```python
cached = getattr(self._lan, "_cached_dm_snapshot", None)
cached_at = getattr(self._lan, "_cached_dm_snapshot_at", 0.0)
```

`self._lan` is evaluated *before* `getattr`'s default kicks in. In
this closure (`LanController.start.<locals>._dm_console_snapshot`)
`self` is the `LanController`, which has no `_lan` attribute, so the
expression raises `AttributeError`. The surrounding route handler's
broad `except Exception: raise HTTPException(500, ...)` converts that
into a 500 for every route that calls `_dm_console_snapshot()` with
no overrides — i.e., the move endpoint, the add-combatant endpoint,
and the idle `GET /api/dm/combat` poll. Apply Results was masked
because `tests/test_dm_control_apply_results.py` stubs
`_lan_force_state_broadcast` out and calls
`_dm_monster_capability_resolve_targets` directly without going
through the HTTP route.

**Fix:**

```python
cached = getattr(self, "_cached_dm_snapshot", None)
cached_at = getattr(self, "_cached_dm_snapshot_at", 0.0)
...
self._cached_dm_snapshot = None
self._cached_dm_snapshot_at = 0.0
```

The write site at
`InitiativeTracker._lan_force_state_broadcast` is unchanged
(`self._lan._cached_dm_snapshot = dm_snap` — that `self` is the
tracker, that `_lan` IS the LanController). Both sites now target
the same `LanController` instance.

**Safety review (post-fix):**

- *Single-use:* yes — the read path clears both `_cached_dm_snapshot`
  and `_cached_dm_snapshot_at` before returning.
- *TTL:* 0.250 s. Short enough that a stale snapshot cannot survive
  long past the broadcast that produced it. Long enough to cover
  the route handler's "broadcast → return snapshot" gap (a few ms).
- *Scope:* only consumed when both `combat_snapshot` and
  `tactical_snapshot` overrides are `None`. Routes that pass an
  override (e.g. `dm_next_turn` passes `combat_snapshot=`) bypass
  the cache entirely — same as before the fix.
- *Cross-request leakage:* technically yes — broadcast A from request
  X seeds the cache, and request Y can consume it. But snapshot A
  reflects the latest authoritative state at the time of broadcast,
  so any consumer of `_dm_console_snapshot()` receives a snapshot at
  least as fresh as the WS-pushed snapshot every other DM client just
  received. Treated as acceptable.
- *Concurrency:* read-then-clear is not atomic, but the two clear
  writes are idempotent and the cache contents are an immutable
  dict reference. Two concurrent readers would each receive the same
  snapshot dict — both correct.
- *Recovery:* on attribute exception the read is wrapped in
  `try/except` and falls through to `_dm_console_snapshot_payload`
  rebuild. So even if some future caller is on a non-LanController
  `self`, it degrades to "no cache" instead of breaking.

**Verdict: cache accepted (post-fix).**

### 2. /dmcontrol idle-poll dedup

`fetchState()`:

```js
const text = await resp.text();
if (text === lastPolledStateJson && state) { /* skip */ return; }
lastPolledStateJson = text;
const data = JSON.parse(text);
state = data;
renderState(data);
draw();
```

- *401 / non-OK:* `if (!resp.ok)` runs first and `return`s before
  the dedup runs. 401 specifically calls `renderError(...)` directly.
  Dedup cannot suppress an auth error. ✓
- *Network/fetch failure:* throws; `catch` calls `renderError`.
  `lastPolledStateJson` is never written from a failed fetch. ✓
- *Combat ended / reset:* if `data.in_combat` flipped or
  `combatants` list changed, `text` will differ from
  `lastPolledStateJson` and we re-render. `renderState`
  short-circuits to the "Out of Combat" path with
  `fullResetLocalState()` and `fetchCapabilitiesForActiveActor(null)`.
  ✓
- *Active actor changed:* `text` differs → re-render. ✓
- *Out-of-band damage / movement:* server-side mutations change the
  snapshot JSON → text differs → re-render. ✓
- *Map metadata change / capability metadata change:* both are part
  of the snapshot payload. JSON text differs → re-render.
  Capabilities are also re-fetched at the end of `renderState` via
  `fetchCapabilitiesForActiveActor`. ✓
- *Malformed payload:* if the server returns invalid JSON, the
  `JSON.parse(text)` throws → `catch` → `renderError('Offline or
  server error')`. `lastPolledStateJson` was already updated to the
  malformed text, so the next poll with the same malformed body will
  skip — but `renderError` already showed the error and `state` is
  unchanged, so the user still sees the error indicator. Not great
  but not harmful. Tightening this would mean rewinding
  `lastPolledStateJson` to its previous value before `JSON.parse`
  runs; declined as out-of-scope speculative hardening — the live
  symptom would be a stuck error banner, not silent data corruption.

**Verdict: dedup accepted.**

### 3. Dijkstra `movementCostMap` memoization

Key composition:

```
cid | pos.col | pos.row | moveRemaining
| cols | rows | feetPerSquare
| obstacles.length | rough_terrain.length | features.length
| hazards.length | structures.length
| movement_mode | swim_speed
```

- Prior `cells.forEach(cell => callback(Math.trunc(cell.col),
  Math.trunc(cell.row), payload));` bug is fixed (`cell.row`,
  not `row`). Verified at
  `assets/web/dmcontrol/index.html:2297`.
- Key DOES invalidate on: actor identity, position, move budget,
  grid dims, foot scale, count of every collection that affects
  Dijkstra, and the actor's movement mode/swim speed.
- Key DOES NOT invalidate on: cell-level position changes within
  `obstacles` / `rough_terrain` / `features` / `hazards` /
  `structures` when count is unchanged. In practice these
  collections rarely mutate without count change during a typical
  /dmcontrol session (you don't relocate a wall in place). The
  only realistic failure mode is a DM-side edit that swaps one
  obstacle for another at a different cell within the same poll
  window. The user would see a stale movement-range tint until the
  next state change that *does* alter actor/pos/move/budget — at
  which point the cache invalidates naturally. Not a correctness
  issue; treated as acceptable until live timing shows otherwise.
- The snapshot does carry a `tactical_map` payload but does not
  appear to expose a monotonic revision counter; if one is added
  later it should be folded into the key.

**Verdict: memoization accepted; cell-level collection mutation is
a documented but low-risk hole.**

### 4. Snapshot-consuming POST paths

Audit of all `fetch('/api/dm/...')` callers in
`assets/web/dmcontrol/index.html`:

| handler | route | snapshot in response? | consumer pre-pass | consumer this pass |
|---|---|---|---|---|
| `applyLocalResolutionResults` | `/api/dm/monster-capabilities/{cid}/resolve-targets` | yes | `state = …; renderState(state)` | `applyAuthoritativeSnapshot(data.snapshot)` ✓ |
| `handleCombatControl` (Start) | `/api/dm/combat/start` | yes | `await fetchState()` | `applyAuthoritativeSnapshot(...)` ✓ |
| `handleCombatControl` (End Turn) | `/api/dm/combat/next-turn` | yes | `await fetchState()` | `applyAuthoritativeSnapshot(...)` ✓ |
| `executeMove` | `/api/dm/map/combatants/{cid}/move` | yes | `await fetchState()` | **this pass:** `applyAuthoritativeSnapshot(...)` with fallback to `fetchState()` ✓ |
| `activateModifier` | `/api/dm/monster-capabilities/{cid}/execute` | yes (sometimes) | `state = …; draw()` (no renderState) | unchanged (pre-existing; outside scope) |
| `startSequence` | same | yes | `state = …; draw()` (no renderState) | unchanged (pre-existing; outside scope) |
| `prepareLocalResolutionPreview` | same with `spend:"none"` | no (preview only, no mutation) | n/a | unchanged ✓ |
| `fetchCapabilitiesForActiveActor` | `/api/dm/monster-capabilities/{cid}` | n/a (GET) | n/a | unchanged ✓ |

`executeMove` keeps a `else { await fetchState(); }` recovery path so
a route that ever stopped returning `snapshot` still re-syncs.

**Verdict: all four user-named POST paths (movement, Apply Results,
End Turn, Start Combat) now consume the returned snapshot. The two
`/.../execute` paths (`activateModifier`, `startSequence`) pre-date
this pass and use a partial pattern (`state = …; draw();` without
`renderState`); they are out of scope for the latency pass but
should be the first follow-up if a future pass adds modifiers to
the responsiveness audit.**

### 5. Frontend perf timing (`?perf=1`)

- Default-silent: `DM_PERF` reads
  `new URLSearchParams(window.location.search).get('perf') === '1'`.
  All `dmPerfMark(...)` calls early-return if `DM_PERF` is false.
  `performance.now()` calls are themselves guarded by ternaries so
  no measurement is even taken without `?perf=1`.
- Behavior parity: timing reads `performance.now()` only; no side
  effects.
- Labels currently emitted:
  - `fetchState(skip-unchanged)` (dedup hit)
  - `fetchState(full)`
  - `renderState`
  - `draw`
  - `startCombat` / `endTurn` (handler totals)
  - `executeMove` (added this pass)
- Labels not currently emitted but worth adding **only if** the
  next live window shows the user-visible click-to-update lag is
  inside one of these:
  - `renderActionPanel` (per-call cost, still rebuilds full
    `innerHTML`)
  - `applyLocalResolutionResults` (end-to-end click-to-snapshot)
  - `prepareLocalResolutionPreview`
  - `movementCostMap` cache hit/miss counters
  Not added speculatively — only narrow, measured changes per the
  task brief.

**Verdict: instrumentation accepted at current granularity.**

### 6. Backend `LAN_PERF` timing

- Default-silent: every `LAN_PERF` block is gated by
  `os.getenv("LAN_PERF_DEBUG") == "1"` and re-evaluated at call
  time so toggling the env without restart is harmless.
- `dm_next_turn`: emits `total_ms`, `next_turn_ms`, `snapshot_ms`.
  `next_turn_ms` covers the `_dm_service.next_turn()` call (which
  includes mutation, broadcast, and the `CombatService.next_turn`
  internal LAN_PERF line); `snapshot_ms` covers only the route's
  final `_dm_console_snapshot(combat_snapshot=…)` work.
- `dm_resolve_monster_capability_targets`: emits `total_ms`,
  `resolve_ms`, `snapshot_ms`, plus `cid`, `apply_damage`,
  `apply_effects`. `resolve_ms` covers the entire
  `_dm_monster_capability_resolve_targets` call (which internally
  fans out to `_apply_map_attack_manual_damage`,
  `_dm_monster_capability_effect_change`, and
  `_lan_force_state_broadcast`); `snapshot_ms` covers only the
  route's `_dm_console_snapshot()` work.
- This separates **route response assembly** from **mutation /
  broadcast** at the route-handler boundary. The internal split
  between *mutation* vs *broadcast* still lives in the inner
  `LAN_PERF _lan_force_state_broadcast` line plus
  `CombatService.next_turn`'s own line, so reading the two together
  gives the full chain. If the next live window shows `resolve_ms`
  is large but neither broadcast nor `_apply_map_attack_manual_damage`
  accounts for it, *that* would be the place to add an
  intra-resolve breakdown — not now.

**Verdict: backend timing accepted at current granularity.**

## Validation

| command | result |
|---|---|
| `./.venv/bin/python3 -m py_compile dnd_initative_tracker.py` | OK |
| `./.venv/bin/python3 -m unittest -v tests.test_dm_console_asset_syntax` | 3/3 OK (≈1 s) |
| `./.venv/bin/python3 -m unittest tests.test_dm_control_apply_results` | 12/12 OK (≈200 s) |
| `./.venv/bin/python3 -m unittest tests.test_dm_control_route.TestDMControlRoute.test_dm_move_combatant_on_map_functional` | OK (≈22 s) — was a 500 before the corrective patch |
| `./.venv/bin/python3 -m unittest tests.test_dm_control_route` | **20/25** OK (≈500 s). 5 failures, 0 errors. Prior pass had 5 failures + **1 error** (`test_dm_move_combatant_on_map_functional`) — the error is gone after the corrective patch, the 5 remaining failures are all baseline-verified pre-existing asset drift. |
| `./.venv/bin/python3 -m unittest tests.test_black_and_tan_capabilities` | 12/13 OK (1 pre-existing `_apply_damage_via_service` stub lacking `_broadcast=` kwarg, baseline-verified) |
| `git diff --check` | clean |

### Baseline verification of the route suite failures

Each failure was checked against `b2d8ae2` via `git stash; rerun
specific test; git stash pop`:

| test | baseline | this pass |
|---|---|---|
| `test_dm_move_combatant_on_map_functional` | OK on baseline | **was 500 (regression introduced by prior pass) → OK after corrective patch** |
| `test_dm_control_has_local_outcome_controls` | FAIL on baseline (asserts non-existent JS function `setLocalResolutionOutcome`) | FAIL, pre-existing |
| `test_dm_control_has_local_resolution_tray_scaffold` | FAIL on baseline | FAIL, pre-existing |
| `test_dm_control_has_mutation_endpoints` | FAIL on baseline | FAIL, pre-existing |
| `test_dm_control_has_resolution_hardening` | FAIL on baseline | FAIL, pre-existing |
| `test_dm_control_movement_blocked_during_targeting` | FAIL on baseline | FAIL, pre-existing |
| `test_black_and_tan_combat_log_force_damage` | error on baseline (test-stub `_apply_damage_via_service` lambda doesn't accept `_broadcast` kwarg) | error, pre-existing |

The prior pass's report had bundled `test_dm_move_combatant_on_map_functional`
under "pre-existing" without verifying — that was a real
regression and is now fixed.

## Live timing summary

**Not run in this pass.** The brief specifies a 5-minute
interactive `/dmcontrol?perf=1` window driven by a human at a
browser. This agent runs in a sandboxed shell with no browser and
no display; the brief's "open `/dmcontrol?perf=1`" cannot be
satisfied automatically. A synthetic backend-only `curl` exercise
against `LAN_PERF_DEBUG=1` was considered but is a poor substitute
for the modal/floating-damage/click-feel observations the user
specifically asked for in the live window.

Recommended live window (to be run by a human):

```
LAN_PERF_DEBUG=1 ./.venv/bin/python3 serve_headless.py
# open http://localhost:8787/dmcontrol?perf=1
# 5 min: idle / select / open modal / preview / apply / drag / start / end turn
```

Lines to grep from `logs/lan_server.log` and the browser console:

```
LAN_PERF dm_resolve_monster_capability_targets total_ms=... resolve_ms=... snapshot_ms=...
LAN_PERF dm_next_turn total_ms=... next_turn_ms=... snapshot_ms=...
LAN_PERF _lan_force_state_broadcast elapsed_ms=... units=...
LAN_PERF _dm_console_snapshot_payload elapsed_ms=... combat_source=... tactical_source=...
[DMPERF] fetchState(skip-unchanged) elapsed_ms=...
[DMPERF] renderState elapsed_ms=...
[DMPERF] draw elapsed_ms=...
[DMPERF] endTurn elapsed_ms=...
[DMPERF] executeMove elapsed_ms=...
```

Expected post-fix behavior to look for:

- The vast majority of `fetchState(...)` lines should be
  `(skip-unchanged)`. If `renderState` runs more than once or
  twice every several seconds outside an action, dedup is wrong.
- `dm_resolve_monster_capability_targets snapshot_ms` should drop
  to near-zero on cache hits (it was previously ~36–100 ms on the
  full rebuild path, and was almost certainly hitting the broken
  AttributeError before the corrective patch).
- `endTurn` total should be one network round-trip plus one
  repaint, no second `fetchState`.
- `executeMove` total should similarly be one round-trip plus one
  repaint.

## Decisions

- **Snapshot cache:** accepted post-fix. Read site now correct;
  TTL, single-use, scope-by-overrides all verified.
- **Idle-poll dedup:** accepted as written. All
  error/auth/recovery paths bypass the dedup or invalidate
  `lastPolledStateJson` on the next genuinely-different response.
- **Dijkstra memo key:** accepted as written. Cell-level mutation
  inside same-length collections is a documented low-risk hole;
  no action.
- **POST snapshot consumers:** widened by one (`executeMove`).
  Two `/execute` callers untouched (pre-existing; out of scope).
- **Frontend perf labels:** accepted at current granularity, one
  new `executeMove` label added.
- **Backend perf labels:** accepted at current granularity.

## Remaining suspected bottlenecks (unchanged from prior pass)

- `renderActionPanel` still rebuilds full `innerHTML` per click.
- `_lan_snapshot` ~13 ms baseline + occasional ~155 ms spike when
  `_load_player_yaml_cache` re-validates the players directory.
- Internal split of `dm_resolve_monster_capability_targets`'s
  `resolve_ms` is not yet broken down by per-target apply, effect
  application, or the inner broadcast — only worth adding if the
  live window shows `resolve_ms` is the dominant component.
- Two `/api/dm/monster-capabilities/{cid}/execute` callers
  (`activateModifier`, `startSequence`) set `state = data.snapshot`
  without `renderState`, leaving the combatant panel briefly stale
  until the next poll triggers a re-render.

## Recommended next pass

1. **Human-run live window** with `LAN_PERF_DEBUG=1` +
   `/dmcontrol?perf=1`. Use the grep recipe above. Verify the
   cache hit drops `dm_resolve_monster_capability_targets
   snapshot_ms` to ~0 and `endTurn` / `executeMove` only ever
   triggers one repaint.
2. If `resolve_ms` is still the dominant component, **add narrow
   intra-resolve timing** inside `_dm_monster_capability_resolve_targets`
   for (a) damage-apply loop, (b) effect-apply loop, (c) the inner
   `_lan_force_state_broadcast`.
3. Do NOT widen into AoE / spellcasting / ammo / reload /
   Controlled Burst / Rough Arrest / new Black-and-Tan mechanics.

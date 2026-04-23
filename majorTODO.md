# Master Tracker: Post-A/Post-B Stabilization and Product Direction

## 1. Purpose

`majorTODO.md` is the durable planning source for platform-level direction and execution order.

Use this file to keep reality ahead of aspiration:
- reflect what is actually landed in code/tests
- keep current priorities clear
- record long-term direction so it survives session boundaries

`todo.md` is still fine for smaller feature/backlog items. This file is for major direction and sequencing.

---

## 2. Current milestone reality (source-of-truth snapshot)

### Status summary

| Track | Status | Reality |
| --- | --- | --- |
| A: DM browser viability | **Complete enough** | `/dm` + `/dm/map` are real operator surfaces and are usable for live encounter operation and map-first workflows. |
| B: Tk-optional/headless host path | **Complete enough** | `serve_headless.py` + `INIT_TRACKER_HEADLESS` + `HeadlessRoot` provide a real non-window host mode for backend + DM/LAN web surfaces. |
| C: Full authority/contract cleanup and product hardening | **In progress** | Important backend seam work landed, but stabilization and corrective product passes now matter more than milestone-chasing. |
| D: Backend/runtime migration exploration | **Exploration only** | Begin planning for an eventual server-resident, TypeScript-first runtime and retirement of Tk from the primary runtime path, but do not treat this as active implementation yet. |

### What this means now

- Tk-host concerns are no longer the central campaign.
- The project has crossed from "prove web/headless feasibility" into "make real sessions reliable and maintainable."
- We should not keep writing plans as if A/B are still open milestones.
- We should also stop pretending the current runtime shape is automatically the long-term endpoint just because headless/browser viability exists.

### Evidence anchors in repo

- DM browser + map workspace routes and map APIs:
  - `dnd_initative_tracker.py` (`/dm`, `/dm/map`, `/api/dm/map/*`)
  - `tests/test_dm_tactical_map_routes.py`
- Headless/Tk-optional host path:
  - `serve_headless.py`
  - `tk_compat.py` (`INIT_TRACKER_HEADLESS`, `HeadlessRoot`)
  - `tests/test_headless_host.py`

---

## 3. Immediate project focus (active priority)

### 3.1 Real-use stabilization and live-session usability

Primary goal: make real table sessions dependable before expanding scope.

Execution shape:
1. Run grouped bugfix passes from real playtesting reports.
2. Prioritize issues that interrupt flow, create state drift, or force DM fallback behavior.
3. Close high-value regressions in coherent batches (not one-off scattered edits).

#### 3.1.a Active live-session blocker bucket (2026-04-22 testing)

These reports now outrank lower-stakes polish work and should drive the next grouped stabilization pass:

- **Headless/LAN startup remains unacceptably slow**: launching the app can still take on the order of minutes in real use. Treat startup latency as an active blocker, not a background nuisance.
- **Encounter setup remains far too slow even after recent combat-service fixes**:
  - adding players still takes multiple minutes before they appear
  - adding enemies is improved from the earlier broken state but is still too slow for live use
  - starting combat / changing turns / other core DM actions still feel like they chug badly
- **Whole-app responsiveness is still suspect under DM setup actions**:
  - `/dm/map` can still appear hung or effectively unusable after setup activity
  - `/dm` can also become unresponsive or feel wedged after core mutations
  - current evidence points to broader hot-path / blocking behavior beyond the specific encounter-population wrapper bugs already fixed
- **Current practical implication**: next stabilization work should focus on hot-path instrumentation, startup/request latency, snapshot/broadcast cost, and blocking mutation flows before returning to lower-priority polish.

#### 3.1.b Recently fixed but still worth retesting

These specific blockers appear to have been addressed in repo and should be kept in regression coverage, but they are no longer the primary planning bullets unless they reappear:

- DM dashboard merge-conflict artifact rendered in live UI
- `CombatService.add_player_profile_combatants` wrapper/service-binding failure caused by Tk fallback attribute lookup
- duplicate `/dm/map` route definition
- the specific inline heavy refresh path in encounter player/enemy population methods
- LAN combat mutation refresh follow-up (2026-04-22): normal `CombatService` mutation broadcasts now run in non-static mode (`include_static=False`), `_lan_force_state_broadcast(include_static=False)` now snapshots with `hydrate_static=False`, and the live-client `_tick` polling snapshot also uses `hydrate_static=False` to avoid rebuilding static payloads on normal combat-state updates.
- Add-Players profile churn follow-up (2026-04-22): `LanController._pcs_payload()` now reuses `self._cached_snapshot["player_profiles"]` when present instead of rebuilding live profiles on every state payload send (fallback to live `_player_profiles_payload()` remains when cache is unavailable), and `_lan_active_aura_contexts()` now preloads player profile cache once per snapshot pass instead of repeatedly calling `_profile_for_player_name()` for each combatant.
- Add-Players YAML cache re-validation follow-up (2026-04-22): `_player_yaml_refresh_interval_s` default raised from 1.0s → 10.0s (resource-pools throttle at `_lan_snapshot` decoupled back to a 1.0s constant so it does not ride the interval), and a new `_PlayerYamlCacheHold` reentrant hold (`tracker._player_yaml_cache_hold()`) short-circuits `_load_player_yaml_cache(force_refresh=False)` while held and the cache is populated. `CombatService.add_player_profile_combatants` now enters the hold for the whole mutation window, and `CombatService._refresh_tracker_outputs` re-enters the hold inside its deferred `_rebuild_table` + `_broadcast_tracker_state` callback so the follow-on LAN snapshot/broadcast also reuses the in-memory cache instead of re-stat'ing the players directory and rewriting `yaml_players_index.json`. Simulated 10-profile Add Players run drops from 11 expensive cache re-validations → 0 during the mutation window (`force_refresh=True` callers still bypass the hold).
- Add-Players redundant re-normalize fix (2026-04-22): `_create_pc_from_profile` now accepts `from_normalized_cache: bool = False`; when True it skips the `_normalize_player_profile` call because the profile already went through normalization when loaded into `_player_yaml_data_by_name`. Both hot callers (`CombatService.add_player_profile_combatants` and the tracker-side `_add_player_profile_combatants_via_service` fallback) pass `from_normalized_cache=True`, with `TypeError` fallbacks to keep older tracker stubs in tests working. Narrow LAN_PERF timing was added inside `_create_pc_from_profile` so per-profile `normalize_ms`/`create_ms`/`summons_ms` are visible under `LAN_PERF_DEBUG=1`. Synthetic repro: 10 profiles drops from 420.6ms (double-normalize path) to 1.6ms (skip path); real profiles include items-registry/magic-item lookups inside `_normalize_player_profile`, so the real-run savings scale higher.

### 3.2 `/dm/map` validation, responsiveness, and workspace correction

Current route/API/test coverage is strong enough to support this as an active validation lane.

Focus now:
- responsiveness during active play
- update cadence and event ordering clarity under live interaction
- practical operator ergonomics during map-first encounter management
- correcting the current map workspace shape so it behaves like a true map-first surface instead of a cramped stacked-card panel

Current live-use UI correction needs called out explicitly:
- **Map view is too small / constrained** inside the current workspace and does not feel like a dedicated full-screen tactical surface.
- **Scrollbars and cramped card layout** are degrading usability across DM workspace menus.
- The DM workspace should move toward **modular, hideable, resizable panels/cards**, so the DM can choose what remains visible during active play.
- DM tracker readability follow-up (2026-04-22): the initiative cards now read as a real combat cockpit instead of sparse rows. `/dm` card rendering now shows explicit PC/ally/enemy badges, red enemy HP emphasis, AC/speed/passive perception/temp HP, defense chips (resistances, vulnerabilities, damage immunities, condition immunities), and compact condition/state badges; the duplicate topbar map link was also removed. This improves glanceability, but it does **not** replace the still-needed modular/resizable workspace pass.
- DM workspace layout follow-up (2026-04-22): `/dm` and `/dm/map` now use a real three-lane workspace shell instead of the old cramped stacked-card layout. The initiative cockpit, tactical map lane, and control lane can now be resized from the browser; cockpit/tools/log can be hidden via panel toggles; secondary control cards collapse instead of permanently consuming vertical space; and the tactical map card now keeps the canvas in the primary lane while advanced map-authoring sections are collapsed into explicit subsections. This materially reduces layout-pressure-driven overflow, though the longer-term panel modularity pass is still not fully done.
- DM setup-lane scanability follow-up (2026-04-22): the right controls lane now groups setup-only cards into labeled `Roster`, `Combat Setup`, `Map Setup`, and `Session` sections so pre-combat/admin tasks scan faster. This was kept frontend-only: no backend route/API behavior, tactical map logic, or tracker-card rendering changed.
- DM live-play lane scanability follow-up (2026-04-22): the right controls lane now adds small labeled `Health`, `Status`, and `Monster Turns` subsections around the existing live-play cards so active-encounter controls scan faster without changing control IDs, backend routes, or combat/tactical behavior.

### 3.3 Performance / hot-path investigation (active, not speculative)

Real testing has now proven this is needed.

Current execution rule:
- do targeted instrumentation and hot-path reduction on the worst live blockers first
- avoid giant theoretical optimization campaigns
- prefer timing/logging and narrow fixes over blind guessing
- avoid expensive smoke/browser work unless explicitly chosen for that session

Current likely investigation targets:
- headless/LAN startup path
- `/dm` render/bootstrap path
- `/dm/map` render/bootstrap path
- combat mutation request paths (add players, add enemies, start combat, turn changes)
- tactical snapshot/build/broadcast costs
- YAML/profile/cache refresh behavior on live mutation paths
- DM next-turn instrumentation follow-up (2026-04-22): `CombatService.next_turn()` now breaks its existing `LAN_PERF` total into `advance_turn_ms`, `rebuild_ms`, `broadcast_ms`, and `snapshot_ms`, and `LanController._dm_console_snapshot_payload()` now logs `combat_snapshot_ms` vs `tactical_snapshot_ms` plus `tactical_source`. This keeps behavior unchanged while exposing whether turn-change latency is dominated by the mutation itself, LAN broadcast, or the follow-up DM response snapshot build.
- DM next-turn snapshot reuse follow-up (2026-04-22): `/api/dm/combat/next-turn` now threads the already-built `CombatService.next_turn()` combat snapshot into `_dm_console_snapshot_payload()` instead of re-calling `CombatService.combat_snapshot()` for the HTTP response. The helper now accepts optional precomputed combat payloads and logs `combat_source=provided|service|missing`, keeping the route payload shape unchanged while removing one duplicate combat snapshot build from the DM next-turn path.

---

## 4. Corrective product passes (must-track)

### 4.1 Spell-management corrective pass (explicitly prioritized)

The existing spell-management model/UI needs a corrective product pass, not incremental patching.

Required outcomes:
1. Remove the generic global "known spells" toggle path.
2. Make wizard known-spell behavior backend-automatic and wizard-specific.
3. Redesign manage-spells around class-aware spell models instead of one broad toggle model.
4. Preserve player flexibility for add/remove/free-spell workflows where applicable.

Notes:
- This pass is product correction + rules-model cleanup.
- Keep compatibility where practical, but do not preserve incorrect abstractions just for inertia.
- Live-session foundation landed: LAN Manage Spells no longer exposes a user toggle for known-spell mode, backend spellbook normalization/save now derives known mode from wizard class data when available, and prepared free-spell persistence no longer drops entries when clients omit `prepared_free_list`.
- Live-session contract pass landed: backend now emits explicit `spellbook_contract` list/mode policy for spell-management, and LAN Manage Spells consumes that contract for tabs plus list ownership/edit gating instead of client-side class/boolean inference.
- Spellbook first-load/stabilization pass (2026-04-21): headless first-WS client now receives populated `spell_presets` (seed snapshot with static data, with live hydration fallback in `_static_data_payload`); browser-executed wizard and non-wizard smoke flows validated in clean single-character mode; added focused unit coverage for `_static_data_payload` preset hydration and for wizard vs non-wizard `_build_live_spellbook_contract` tab shape. Follow-up smoke reliability pass now runs multi-profile spell-manager coverage in isolated browser contexts (fresh claim/session per profile), removing synthetic cross-player contamination from harness reuse while keeping real one-claim-per-session flow semantics.
- Remaining priority in this area is no longer “basic contract cleanup landed” but “keep it stable enough without letting it outrank broader live-session slowness.”

### 4.2 Adjacent rules/model corrective cleanup

When corrective passes expose mismatches between backend rules semantics and current UI assumptions, fix the model boundary instead of adding more UI-side exception logic.

---

## 5. Long-term product direction (do not lose this)

### 5.1 Authoring workflow shift

Long-term direction is explicit:
- stop using AI as the normal path for every supported content addition
- build robust DM-facing browser authoring/admin tools for supported content
- keep AI mainly for foundational backend work and advanced/unsupported mechanics
- replace backend-shaped freeform entry with guided, constrained, schema-aware tooling

### 5.2 Likely first authoring slices

1. Magic item builder (first slice)
2. Equipment / armor / weapons / consumables
3. Simple feature authoring

This sequence should stay visible across sessions unless real implementation evidence changes it.

### 5.3 Potential backend/runtime migration (exploration track)

This is **not** active implementation yet, but it should now remain visible in major planning.

#### Desired end state

- server-resident app that can stay running continuously
- VPN/browser access as the normal operating model
- Tk retired from the **primary runtime path**
- TypeScript-first backend/runtime target for the long-term hosted/web system
- explicit backend authority and contracts for realtime DM/LAN/tactical state

#### Why this is being considered now

- headless/browser viability is proven enough that the project no longer needs Tk as the center of gravity
- current runtime architecture still chugs badly in real use even when actions technically succeed
- the product direction increasingly fits a server-resident web system more than a desktop-origin app with web surfaces attached
- the user does not plan to return to the desktop/Tk workflow as a normal operating mode

#### Migration rule

- **No big-bang rewrite.**
- Any serious migration should be **incremental / strangler-style**, with old and new paths coexisting during transition.
- The goal is not “rewrite Python because Python is bad”; the goal is to replace the current runtime shape with a cleaner, server-resident web architecture where that is genuinely worth the cost.

#### Likely first migration slice if exploration becomes implementation

- realtime tactical / encounter backend
- DM + LAN state authority and synchronization path
- combat mutation command path

#### Promotion gates before this becomes active implementation

1. hotspot instrumentation on current live blockers
2. bounded-context definition for the first extracted slice
3. a narrow vertical-slice spike / proof-of-approach
4. explicit go/no-go decision on cost vs benefit

#### Important caution

The previous Tk→web/headless migration already consumed substantial time and money. Do not let this become an unbounded rewrite campaign driven only by frustration. Treat this as a strategic exploration track until there is evidence that a staged migration is worth the cost.

---

## 6. Deferred / later (important, not top priority right now)

These remain important but are **not** current top-of-stack while stabilization is active:

1. Production/install/update polish beyond current safety baseline
2. Visual/front-end polish and broad UI refinement that is not directly tied to active live-session blockers
3. Advanced cleanup of legacy desktop/editor surfaces not required for current stabilization or migration exploration
4. Broad release/packaging pushes before real-play stability is proven
5. Detailed runtime migration RFC / implementation planning docs before the exploration track is intentionally promoted

### 6.1 Level-11 player follow-up (2026-04-22) — landed

The focused player-file follow-up is now reflected in repo:

- **Dorian** is now authored as Paladin 11 with the Radiant Strikes
  `damage_riders` stanza, Channel Divinity 3, prepared-spell target `10`,
  and level-11 slot ceilings (`4/3/3`). HP was left unchanged; Lay on
  Hands max now reflects the higher paladin level while preserving the
  current spent-state.
- **Malagrou** already had the level 11 class/resource bump in YAML; the
  follow-up here was keeping `Weapon Mastery Choices` at current `4` and
  updating the Relentless Rage descriptor so it matches the landed backend
  behavior instead of the old manual-placeholder wording.
- **Old Man** is now level 11 in YAML and keeps Fly/Swim defaults aligned
  with walk speed so `cycle_movement_mode` continues to surface the
  Stride of the Elements travel modes cleanly. HP was left unchanged.
- **Vicnor** remains Rogue 3 / Warlock 8 with the 2024 warlock chassis +
  legacy Noble Genie direction preserved. The 5th invocation is now
  represented as an explicit pending-choice placeholder instead of being
  invented, and the missing Warlock 8 ASI/feat is left explicitly
  unresolved until player input arrives.
- **Remaining follow-up after this pass**: Vicnor still needs actual
  player input to replace the pending Warlock 8 invocation/ASI placeholders,
  and the updated player files should still get normal in-app/at-table
  eyeball verification during live use.
- **Throat Goat (Bard 9 / Warlock 2, level 11)**: backend already
  auto-derives free/always-prepared via `_feature_always_prepared_spell_slugs`,
  so Beguiling Magic and Mantle of Majesty entries in features add their
  spells to prepared + free without YAML redundancy. Two multiclass gaps
  are **not** in scope for this pass and should be tracked for a later
  spell-management corrective slice:
  1. `prepared_spells.max_formula` is a single static value; 2024 PHB
     Bard 9 = 14 and Warlock 2 = 3 per-class prep budgets are not modeled
     separately in the normalizer.
  2. `pact_magic_slots` vs `spell_slots` are two distinct pools but the
     prepared list does not track per-class origin for a spell. Multiclass
     warlock/other casters work in practice because the UI surfaces both
     slot groups, but there is no backend constraint that forces warlock
     spells to use pact slots.

### 6.2 Eldramar wand migration (2026-04-22) — landed

Eldramar's `shocking-grasp` and `lightning-bolt` entries were removed
from his wizard cantrips/known/prepared lists; the `Wand of Sparking`
magic item now grants both via `always_prepared_spells` and also exposes
a `wand_of_sparking_lightning_bolt` pool (1/LR) with a `spells.casts`
mapping so the lightning-bolt cast consumes the item pool instead of a
wizard slot. The pool state is tracked under the wand's
`inventory.items[].state.pools` so long-rest reset and current-charge
persistence route through the existing item-granted pool path.

### 6.3 Fred Bhall backend pass (2026-04-23) — explicit-choice pass landed

Fred's first bounded backend/runtime support pass is now reflected in repo:

- `players/fred_figglehorn.yaml` remains the source of truth for this pass:
  Warlock 8 / `Acolyte of Bhall`, `murderspawn`, `cull_the_weak`,
  `blood_in_the_air`, and the `murderous_intent` short-rest pool are all
  authored in YAML and were used directly for the runtime work.
- `Murderspawn` now gains Murderous Intent in backend runtime on the real
  single-target attack/spell damage paths:
  1. first hostile-damage event each turn grants `+1 MI`
  2. dropping a creature to `0 HP` grants an additional `+1 MI`
  3. gain is clamped to the current pool max and no longer relies on a
     manual table-side increment for those paths
- `Murderspawn` spend now has a small explicit backend seam instead of a
  table-side default:
  send `murderspawn_spend` on a qualifying Fred attack / spell-target
  request, the backend spends that exact amount from the existing
  `murderous_intent` pool, adds the matching necrotic bonus damage, and
  preserves the choice through Shield / Absorb Elements / Interception
  resumes via the request contract payload.
- `Cull the Weak` / `Blood in the Air` threshold awareness is now carried in
  attack/spell result payloads as backend-produced Bhall awareness state:
  below-half HP, below-quarter HP, within-30-feet, and which authored
  awareness threshold is currently active.
- `Blood in the Air` no longer auto-picks a branch. The backend now expects
  an explicit `blood_in_the_air_choice` on the qualifying Fred damage event:
  - `reactions` applies the Wisdom-save-gated `reactions_blocked` rider that
    clears at the start of the target's next turn
  - `move` uses a bounded destination seam
    (`blood_in_the_air_destination_col` / `_row`) to relocate Fred up to
    `10 ft` without provoking opportunity attacks
- Important authored-YAML reality: the current Fred YAML says the
  `blood_in_the_air` damage rider triggers on damaging a creature below
  half HP, while quarter HP is only the awareness threshold. Runtime follows
  that authored source for now rather than older out-of-repo drafts.
- Still pending after this pass:
  1. There is still no frontend prompt/UI flow for Fred's Bhall choices;
     the backend seam is request-driven for now.
  2. Murderspawn spend qualification is intentionally conservative:
     weapon hits plus warlock cantrips / prepared warlock spells from Fred's
     authored sheet, not every possible future spell-origin edge case.
  3. Murderspawn gain is not yet broadened across every indirect/AoE/triggered
     damage path; this pass is intentionally limited to the current direct
     single-target player attack/spell runtime.

---

## 7. Working guardrails for major passes

- Prefer stabilization evidence over milestone rhetoric.
- Keep backend authority and explicit contracts moving forward, but prioritize reliability in real sessions.
- Avoid broad roadmap churn that ignores playtest-driven defect reality.
- Do not re-center planning around desktop-first host concerns.
- Avoid expensive smoke/browser work unless the session intentionally chooses to spend usage on it.
- If migration exploration begins, keep it incremental and bounded; do not let it erase the need to understand current hot paths.
- Keep `majorTODO.md` synchronized whenever major reality shifts.

---

## 8. Update protocol for future agents/sessions

When completing a substantial pass:
1. Update this file in the same PR/patch.
2. Mark what changed in real status terms (`complete enough`, `active`, `deferred`, `exploration only`).
3. Keep immediate focus, corrective product passes, migration exploration, long-term direction, and deferred work explicitly separated.
4. Remove stale priorities instead of preserving them as historical clutter.

If code/tests and this file disagree, fix this file promptly.

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

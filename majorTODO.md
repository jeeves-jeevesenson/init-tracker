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

### What this means now

- Tk-host concerns are no longer the central campaign.
- The project has crossed from "prove web/headless feasibility" into "make real sessions reliable and maintainable."
- We should not keep writing plans as if A/B are still open milestones.

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

- **DM dashboard merge-conflict artifact visible in live UI**: stray conflict-marker text (`<<<<<<< HEAD`, `=======`, `>>>>>>> …`) is rendering near the Map Setup section. Treat this as a real shipped UI corruption bug, not cosmetic noise.
- **Add Players path appears functionally broken and/or severely blocked**: live testing hit `CombatService.add_player_profile_combatants exception: 'function' object has no attribute 'add_player_profile_combatants'`. In the same session, player adds either failed or took multiple minutes before appearing.
- **Add Enemies path appears similarly hung or non-completing** during live encounter setup.
- **Whole app can stall after encounter setup actions**: after adding players / creating a map, `/dm/map` loaded forever and even `/` stopped responding, indicating a likely server-side hang, blocking operation, or deadlocked/very-long-running update path.
- **Practical priority implication**: next stabilization work should focus on encounter add flows, service binding/dispatch correctness, request latency/hangs, and whole-app responsiveness under DM setup actions before returning to lower-priority polish.


### 3.2 `/dm/map` validation and responsiveness

Current route/API/test coverage is strong enough to support this as an active validation lane.

Focus now:
- responsiveness during active play
- update cadence and event ordering clarity under live interaction
- practical operator ergonomics during map-first encounter management

### 3.3 Performance follow-up (conditional, not assumed)

Do targeted performance work only when real testing shows sustained issues.

Do **not** run speculative optimization campaigns by default.

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

---

## 6. Deferred / later (important, not top priority right now)

These remain important but are **not** current top-of-stack while stabilization is active:

1. Production/install/update polish beyond current safety baseline
2. Visual/front-end polish and broad UI refinement
3. Advanced legacy desktop/editor cleanup not required for current stabilization goals
4. Broad release/packaging pushes before real-play stability is proven

---

## 7. Working guardrails for major passes

- Prefer stabilization evidence over milestone rhetoric.
- Keep backend authority and explicit contracts moving forward, but prioritize reliability in real sessions.
- Avoid broad roadmap churn that ignores playtest-driven defect reality.
- Do not re-center planning around desktop-first host concerns.
- Keep `majorTODO.md` synchronized whenever major reality shifts.

---

## 8. Update protocol for future agents/sessions

When completing a substantial pass:
1. Update this file in the same PR/patch.
2. Mark what changed in real status terms (`complete enough`, `active`, `deferred`).
3. Keep immediate focus, corrective product passes, long-term direction, and deferred work explicitly separated.
4. Remove stale priorities instead of preserving them as historical clutter.

If code/tests and this file disagree, fix this file promptly.

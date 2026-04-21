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

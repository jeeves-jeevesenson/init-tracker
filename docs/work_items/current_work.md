# Current Work Ledger

This is the authoritative source for what the Orchestrator is currently doing.
If an item is not marked as **Active** here, it is NOT current work.

---

## Current Status

<!-- ACTIVE_WORK_STATUS_START -->
- **Status:** Idle
- **Current Work Item:** None
- **Active Gate:** None
- **Allowed Next Action:** Commit the completed place-command slice after reviewing scoped diff/status, or open the next bounded server-runtime extraction work item.
<!-- ACTIVE_WORK_STATUS_END -->

---

## Active Work Table

| ID | Title | Status | Goal |
| --- | --- | --- | --- |
<!-- ACTIVE_WORK_TABLE_START -->
<!-- ACTIVE_WORK_TABLE_END -->

---

## Recently Completed Table

| ID | Title | Completion Date | Evidence |
| --- | --- | --- | --- |
| BUG-20260614-weapon-attacks-reload-fail | Weapon attacks / reload fail | 2026-06-26 | Closed in `6d14706`; focused unit tests passed; JS syntax check passed; diff check passed; developer browser smoke passed; final weapon reload / ammo / Multiattack behavior accepted. See `docs/work_items/active/BUG-20260614-weapon-attacks-reload-fail-smoke-failure-20260626.md`. |
<!-- COMPLETED_WORK_TABLE_START -->
| WORK-20260629-runtime-facade-queue-command-place | Queue-backed facade command for combatant place/reposition | 2026-06-29 | Completed implementation slice; migrated only POST /api/dm/map/combatants/{cid}/place through ServerRuntimeFacade and the queue adapter seam, preserving existing behavior and focused tests. See [completed/WORK-20260629-runtime-facade-queue-command-place.md](completed/WORK-20260629-runtime-facade-queue-command-place.md). |
| WORK-20260629-runtime-facade-next-queue-command-selection-2 | Runtime facade next queue command selection 2 | 2026-06-29 | Completed evidence/planning slice; evaluated place, move, and AoE command candidates; recommended migrating POST /api/dm/map/combatants/{cid}/place next. See [completed/WORK-20260629-runtime-facade-next-queue-command-selection-2.md](completed/WORK-20260629-runtime-facade-next-queue-command-selection-2.md). |
| WORK-20260629-runtime-facade-queue-command-auras | Queue-backed facade command for map aura overlays | 2026-06-29 | Completed implementation slice; migrated only POST /api/dm/map/overlays/auras through ServerRuntimeFacade and the queue adapter seam, preserving existing behavior and focused tests. See [completed/WORK-20260629-runtime-facade-queue-command-auras.md](completed/WORK-20260629-runtime-facade-queue-command-auras.md). |

| WORK-20260629-runtime-facade-next-queue-command-selection | Runtime facade next queue command selection | 2026-06-29 | Completed evidence/planning slice; evaluated move, place, and set_auras_enabled candidates; recommended migrating POST /api/dm/map/overlays/auras next. See [completed/WORK-20260629-runtime-facade-next-queue-command-selection.md](completed/WORK-20260629-runtime-facade-next-queue-command-selection.md). |
| WORK-20260629-runtime-facade-queue-command-facing | Queue-backed facade command for combatant facing | 2026-06-29 | Completed implementation slice; migrated only POST /api/dm/map/combatants/{cid}/facing through ServerRuntimeFacade and the queue adapter seam, preserving Tk queue authority and focused tests. See [completed/WORK-20260629-runtime-facade-queue-command-facing.md](completed/WORK-20260629-runtime-facade-queue-command-facing.md). |
| WORK-20260629-runtime-facade-queue-command-selection | Runtime facade queue command selection | 2026-06-29 | Completed evidence/planning slice; selected POST /api/dm/map/combatants/{cid}/facing as the first low-risk production command to route through the facade queue adapter. See [completed/WORK-20260629-runtime-facade-queue-command-selection.md](completed/WORK-20260629-runtime-facade-queue-command-selection.md). |
| WORK-20260629-runtime-facade-queue-adapter | Runtime facade queue adapter seam | 2026-06-29 | Completed implementation slice; added facade-side queue adapter seam and focused tests for success, timeout, failure/error mapping, traces, and fail-closed unknown commands. No production routes migrated and no LanController/gameplay behavior changed. See [completed/WORK-20260629-runtime-facade-queue-adapter.md](completed/WORK-20260629-runtime-facade-queue-adapter.md). |
| WORK-20260629-runtime-facade-queue-adapter-evidence | Runtime facade queue adapter evidence | 2026-06-29 | Completed evidence/planning slice; documented LanController._actions queue flow, action-state registry fields, queue metrics, Tk thread authority, timeout/failure/trace semantics, and selected the facade-side queue adapter seam as the next bounded implementation slice. See [completed/WORK-20260629-runtime-facade-queue-adapter-evidence.md](completed/WORK-20260629-runtime-facade-queue-adapter-evidence.md). |
| WORK-20260629-runtime-facade-next-boundary-evidence | Runtime facade next boundary evidence | 2026-06-29 | Completed evidence/planning slice; documented current facade surface, trace/status access gap, route/runtime boundary findings, LAN/Tk queue authority, and selected queue-adapter evidence as the next safest migration step. See [completed/WORK-20260629-runtime-facade-next-boundary-evidence.md](completed/WORK-20260629-runtime-facade-next-boundary-evidence.md). |
| WORK-20260628-command-queue-observability-foundation | Command queue observability foundation | 2026-06-28 | Completed in `153c23d`; added runtime command lifecycle constants, `RuntimeCommandTrace`, and focused trace coverage for the spell-color facade path. See [completed/WORK-20260628-command-queue-observability-foundation.md](completed/WORK-20260628-command-queue-observability-foundation.md). |
| WORK-20260628-command-queue-semantics | Command queue semantics | 2026-06-28 | Completed in `fb33b9f`; defined facade-owned command gateway semantics, threading authority, lifecycle/failure/observability model, and selected `WORK-20260628-command-queue-observability-foundation`. See [completed/WORK-20260628-command-queue-semantics.md](completed/WORK-20260628-command-queue-semantics.md). |
| WORK-20260628-command-queue-spell-color | Spell color command boundary | 2026-06-28 | Completed in `fa1e79f`; routed only `POST /api/spells/{spell_id}/color` through the runtime facade command boundary, preserved behavior, and added focused tests. See [completed/WORK-20260628-command-queue-spell-color.md](completed/WORK-20260628-command-queue-spell-color.md). |
| WORK-20260628-command-queue-slice-selection | Command queue slice selection | 2026-06-28 | Completed in `22d5637`; selected `POST /api/spells/{spell_id}/color` as the first low-risk command-queue candidate and proposed `WORK-20260628-command-queue-spell-color`. See [completed/WORK-20260628-command-queue-slice-selection.md](completed/WORK-20260628-command-queue-slice-selection.md). |
| WORK-20260628-runtime-facade-contracts | Runtime facade command and snapshot contracts | 2026-06-28 | Completed in `2244f09`; added explicit command/snapshot contract dataclasses and fail-closed facade boundaries; focused tests and scope validation passed. See [completed/WORK-20260628-runtime-facade-contracts.md](completed/WORK-20260628-runtime-facade-contracts.md). |
| WORK-20260628-runtime-facade-skeleton | Runtime facade skeleton | 2026-06-28 | Completed in `ac210c6`; added narrow `ServerRuntimeFacade`, wired app factory ownership via `app.state.runtime`, preserved health/readiness, added focused tests, and passed scoped validation. See [completed/WORK-20260628-runtime-facade-skeleton.md](completed/WORK-20260628-runtime-facade-skeleton.md). |
| BUG-20260627-manage-spells-free-spell-limit-and-save-failures | Manage Spells free spell limits and save failures | 2026-06-27 | Fixed free spell add/remove behavior and Unicode/Cyrillic player profile save lookup; py_compile passed; spellbook unittest passed; A0 gate passed; diff check passed; developer browser smoke passed. See [completed/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md](completed/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md). |
| BUG-20260626-spell-multiattack-ranged-fail | Spell Multiattack and ranged attack failure | 2026-06-27 | Fixed upcast ranged spell attack pending authority and multi-projectile reuse; repaired Magic Missile and Eldritch Blast YAML scaling; corrected runtime user preset seeding and hashing cache; fixed unconditional forced save check; repaired monster/combatant max HP preservation on damage; verified backend-only single-log-line outputs. Passed all 108 tests. See [completed/BUG-20260626-spell-multiattack-ranged-fail.md](completed/BUG-20260626-spell-multiattack-ranged-fail.md). |
| BUG-20260626-aura-of-protection-grid-snap | Aura of Protection grid snap offset | 2026-06-26 | [completed/BUG-20260626-aura-of-protection-grid-snap.md](completed/BUG-20260626-aura-of-protection-grid-snap.md) |
| BUG-20260614-reactions-hold-combat | Reactions can hold up combat | 2026-06-26 | [completed/BUG-20260614-reactions-hold-combat.md](completed/BUG-20260614-reactions-hold-combat.md) |
| WORK-20260619-orchestrator-agy-context-hygiene | Orchestrator + AGY context hygiene | 2026-06-19 | [completed/WORK-20260619-orchestrator-agy-context-hygiene.md](completed/WORK-20260619-orchestrator-agy-context-hygiene.md) |
| BUG-20260614-aoe-preview-mismatch | AoE preview mismatch (Target count/location) | 2026-06-17 | [completed/BUG-20260614-aoe-preview-mismatch.md](completed/BUG-20260614-aoe-preview-mismatch.md) |
| BUG-20260614-fireball-damage-roll-inconsistent | Fireball damage rolled separately per target | 2026-06-17 | [completed/BUG-20260614-fireball-damage-roll-inconsistent.md](completed/BUG-20260614-fireball-damage-roll-inconsistent.md) |
| BUG-20260614-player-1080p-header-overflow | 1080p header overflow / Battle Log invisible | 2026-06-17 | [completed/BUG-20260614-player-1080p-header-overflow.md](completed/BUG-20260614-player-1080p-header-overflow.md) |
| BUG-20260614-player-mount-lockout | Player mount lockout / movement failure | 2026-06-17 | [completed/BUG-20260614-player-mount-lockout.md](completed/BUG-20260614-player-mount-lockout.md) |
| BUG-20260614-player-fireball-preview-applies-one-target | Fireball preview mismatch | 2026-06-16 | [completed/BUG-20260614-player-fireball-preview-applies-one-target.md](completed/BUG-20260614-player-fireball-preview-applies-one-target.md) |
| BUG-20260614-player-spell-slots-not-syncing | Player spell slot/resource sync does not update UI after cast or manual override | 2026-06-14 | [completed/BUG-20260614-player-spell-slots-not-syncing.md](completed/BUG-20260614-player-spell-slots-not-syncing.md) |
| WORK-20260604-black-tan-combat-exploration | AI/Browser-Driven Combat Bug Exploration | 2026-06-14 | [completed/WORK-20260604-black-tan-combat-exploration.md](completed/WORK-20260604-black-tan-combat-exploration.md) |
| WORK-20260603-browser-smoke-harness-scorcher-ignite-ground | Browser Automation Smoke Harness Foundation (Pilot: Scorcher) | 2026-06-04 | [completed/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md](completed/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md) |
| WORK-20260530-black-tan-vda-scorcher-automation | Automate Black and Tan monster control and add VDA Scorcher | 2026-06-04 | docs/work_items/completed/WORK-20260530-black-tan-vda-scorcher-automation.md |
| ITR-20260529-A0-08 | Add current work ledger and long-term planning GPT workflow | 2026-05-30 | docs/work_items/completed/ITR-20260529-A0-08.md |
| WORK-20260628-port-external-research | Port external server runtime research | 2026-06-28 | Imported external research docs and server-runtime planning foundation in commit `a210eca`. No app implementation. |
| WORK-20260628-server-runtime-roadmap | Server runtime extraction roadmap | 2026-06-28 | Distilled imported ASGI/runtime research into repo-specific target architecture, decision list, phased roadmap, and first future implementation candidate. No app implementation. |
| WORK-20260628-server-first-health-shell | Server-first health and app factory shell | 2026-06-28 | Implemented app factory health/readiness seam in `af88529`; focused unit/headless validations passed; developer smoke confirmed `/health`, `/api/health`, `/ready`, and `/api/ready` return HTTP 200 with expected JSON. Smoke log: `logs/smoke/WORK-20260628-server-first-health-shell_smoke-server_20260628-220510.log`. Debug trace: `logs/debug-trace-20260628-220510.jsonl`. |
<!-- COMPLETED_WORK_TABLE_END -->

---

## Superseded Plans Table

| ID | Title | Superseded By | Reason |
| --- | --- | --- | --- |
<!-- SUPERSEDED_WORK_TABLE_START -->
<!-- SUPERSEDED_WORK_TABLE_END -->

---

## Unresolved Bugs Queue (Triaged)

| ID | Title | Severity | Note |
| --- | --- | --- | --- |
<!-- UNRESOLVED_BUGS_QUEUE_START -->
| BUG-20260614-multiattack-eldritch-blast-failures | Multiattack / Eldritch Blast failures | S1 | Triaged unresolved; needs exact actor/target/error evidence. |
| BUG-20260614-dm-zero-hp-enemies-not-removed | DM 0 HP enemy override does not remove enemy | S1 | Triaged unresolved; needs DM override repro/evidence. |
| BUG-20260614-fount-of-moonlight-failed | Fount of Moonlight failed | S1 | Triaged unresolved; vague report, needs current repro/evidence. |
| BUG-20260614-dm-ac-display-wrong | DM AC display wrong | S2 | Triaged unresolved; needs combatant expected-vs-actual evidence. |
| BUG-20260614-enemy-hp-redaction-manual-adjust | Enemy HP redaction after manual adjust | S2 | Triaged unresolved; potential hidden-HP leak, needs log evidence. |
| BUG-20260614-mounting-token-link-buggy | Mounting token link intermittent desync | S2 | Triaged unresolved; distinct from completed mount-lockout bug. |
| BUG-20260614-divine-smite-manual-modal | Divine Smite manual modal support | S3 | Triaged backlog/design; product decision needed before app work. |
| BUG-20260614-end-turn-reminders | End turn reminders | S3 | Triaged backlog/design; feature definition needed. |
| BUG-20260614-enemy-name-generator-yaml-subnames | Enemy YAML subname/name generator | S3 | Triaged backlog/design; schema examples needed. |
| BUG-20260614-player-guns-missing | Add guns for all players | S3 | Triaged backlog/data; needs character/equipment list. |
<!-- UNRESOLVED_BUGS_QUEUE_END -->

---

## Reopen Conditions

An item may only be reopened if:
1. A regression is found in the specific files touched by the item.
2. The original goal was not met as proven by new smoke/test evidence.
3. The developer explicitly requests a reopen.

---

## Orchestrator Refusal Rule

**If no active work item exists in this section, do not invent one from old docs, majorTODO.md, or historical runtime reports.**

In the absence of an active work item, the Orchestrator MUST stop and ask the developer whether to:
1. Open a new bug report.
2. Start a new planning/research pass.
3. Continue to the next recovery gate.
4. Perform smoke testing.
5. Commit/Push current changes.
6. Deploy to production.

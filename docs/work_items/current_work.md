# Current Work Ledger

This is the authoritative source for what the Orchestrator is currently doing.
If an item is not marked as **Active** here, it is NOT current work.

---

## Current Status

<!-- ACTIVE_WORK_STATUS_START -->
- **Status:** Active
- **Current Work Item:** WORK-20260628-runtime-facade-skeleton
- **Active Gate:** Runtime Facade Skeleton Gate
- **Allowed Next Action:** Draft or run one bounded AGY implementation task for the runtime facade skeleton. Continue server-runtime extraction migration. Do not triage unrelated bug inbox dirt, logs/context, frontend, route migration, queue, cache, deploy, or random cleanup.
<!-- ACTIVE_WORK_STATUS_END -->

---

## Active Work Table

| ID | Title | Status | Goal |
| --- | --- | --- | --- |
<!-- ACTIVE_WORK_TABLE_START -->
| WORK-20260628-runtime-facade-skeleton | Runtime facade skeleton | Active | Add the smallest runtime facade skeleton behind the server app factory seam; no gameplay route migration, command queue, snapshot cache, or frontend work. |
<!-- ACTIVE_WORK_TABLE_END -->

---

## Recently Completed Table

| ID | Title | Completion Date | Evidence |
| --- | --- | --- | --- |
| BUG-20260614-weapon-attacks-reload-fail | Weapon attacks / reload fail | 2026-06-26 | Closed in `6d14706`; focused unit tests passed; JS syntax check passed; diff check passed; developer browser smoke passed; final weapon reload / ammo / Multiattack behavior accepted. See `docs/work_items/active/BUG-20260614-weapon-attacks-reload-fail-smoke-failure-20260626.md`. |
<!-- COMPLETED_WORK_TABLE_START -->
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

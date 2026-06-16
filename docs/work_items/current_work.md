# Current Work Ledger

This is the authoritative source for what the Orchestrator is currently doing.
If an item is not marked as **Active** here, it is NOT current work.

---

## Current Status

<!-- ACTIVE_WORK_STATUS_START -->
- **Status:** Idle
- **Current Work Item:** None
- **Active Gate:** None
- **Allowed Next Action:** Choose next bug promotion, deploy/push, planning, or idle.
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
<!-- COMPLETED_WORK_TABLE_START -->
| BUG-20260614-player-fireball-preview-applies-one-target | Fireball preview mismatch | 2026-06-16 | [completed/BUG-20260614-player-fireball-preview-applies-one-target.md](completed/BUG-20260614-player-fireball-preview-applies-one-target.md) |
| BUG-20260614-player-spell-slots-not-syncing | Player spell slot/resource sync does not update UI after cast or manual override | 2026-06-14 | [active/BUG-20260614-player-spell-slots-not-syncing.md](active/BUG-20260614-player-spell-slots-not-syncing.md) |
| WORK-20260604-black-tan-combat-exploration | AI/Browser-Driven Combat Bug Exploration | 2026-06-14 | [completed/WORK-20260604-black-tan-combat-exploration.md](completed/WORK-20260604-black-tan-combat-exploration.md) |
| WORK-20260603-browser-smoke-harness-scorcher-ignite-ground | Browser Automation Smoke Harness Foundation (Pilot: Scorcher) | 2026-06-04 | [completed/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md](completed/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md) |
| WORK-20260530-black-tan-vda-scorcher-automation | Automate Black and Tan monster control and add VDA Scorcher | 2026-06-04 | docs/work_items/completed/WORK-20260530-black-tan-vda-scorcher-automation.md |
| ITR-20260529-A0-08 | Add current work ledger and long-term planning GPT workflow | 2026-05-30 | docs/work_items/completed/ITR-20260529-A0-08.md |
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
| BUG-20260614-player-mount-lockout | Player mount lockout / movement failure | P1 | High priority blocker, queued behind Fireball resolution. |
| BUG-20260614-player-1080p-header-overflow | 1080p header overflow / Battle Log invisible | P2 | UX issue, queued. |

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

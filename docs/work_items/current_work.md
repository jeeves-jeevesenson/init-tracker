# Current Work Ledger

This is the authoritative source for what the Orchestrator is currently doing.
If an item is not marked as **Active** here, it is NOT current work.

---

## Current Status

<!-- ACTIVE_WORK_STATUS_START -->
- **Status:** Active
- **Current Work Item:** WORK-20260530-black-tan-vda-scorcher-automation: Automate Black and Tan monster control and add VDA Scorcher
- **Active Gate:** Gate 4: VDA Scorcher Stat Block & Lore
- **Allowed Next Action:** Implement VDA Scorcher stat block and Scorched Earth Protocol.
<!-- ACTIVE_WORK_STATUS_END -->

---

## Active Work Table

| ID | Title | Status | Goal |
| --- | --- | --- | --- |
<!-- ACTIVE_WORK_TABLE_START -->
| WORK-20260530-black-tan-vda-scorcher-automation | Automate Black and Tan monster control and add VDA Scorcher | Active | Add Scorcher and remove all manual reminders from Black and Tan capabilities. |
<!-- ACTIVE_WORK_TABLE_END -->

---

## Recently Completed Table

| ID | Title | Completion Date | Evidence |
| --- | --- | --- | --- |
<!-- COMPLETED_WORK_TABLE_START -->
| ITR-20260529-A0-08 | Add current work ledger and long-term planning GPT workflow | 2026-05-30 | docs/work_items/completed/ITR-20260529-A0-08.md |
<!-- COMPLETED_WORK_TABLE_END -->

---

## Superseded Plans Table

| ID | Title | Superseded By | Reason |
| --- | --- | --- | --- |
<!-- SUPERSEDED_WORK_TABLE_START -->
<!-- SUPERSEDED_WORK_TABLE_END -->

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

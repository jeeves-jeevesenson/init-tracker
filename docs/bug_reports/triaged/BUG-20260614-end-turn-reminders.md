# BUG-20260614-end-turn-reminders

## Triage Disposition

- **Status**: Triaged backlog/design
- **Triage Date**: 2026-06-26
- **Disposition**: Product/design clarification before app work.
- **Reason**: This is a feature/UX request unless tied to a missing existing reminder.

* status: inbox
* severity: S3
* priority: P2
* reported date: 2026-06-14
* reported by: developer
* area: Turn Flow / UX
* confidence: medium

## Summary

The developer wants end turn reminders.

## User-visible impact

Players or the DM may forget to end turns or miss required end-of-turn actions/effects, slowing combat.

## Observed behavior

The uploaded debugging notes say: "end turn reminders."

## Expected behavior
The app should provide useful end-turn reminders, such as unresolved reactions, concentration, ongoing effects, conditions, saves, or resource prompts, depending on product design.

## Surface clarification needed
This is a feature/UX request. Developer decision is needed on whether this should be a player-facing popup, a DM-facing notification, or a subtle UI indicator.

## Reproduction steps
Not applicable yet; this is a feature/UX request unless tied to a specific missed reminder.


## Environment

Unknown.

## Evidence provided

Developer note only.

## Missing evidence

* Which reminders are required.
* Which surface should show them.
* Whether reminders should be player-facing, DM-facing, or both.
* Whether this is a bug in an existing reminder system or a new feature.

## Suspected areas / hypotheses

* Turn flow UI.
* Active effects/status system.
* Player/DM notification design.
* Do not treat this as root cause.

## Related history

The developer also noted reactions can hold up combat, which may overlap with end-turn UX.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this belongs in backlog, evidence capture, Gemini task, Codex task, or smoke coverage.

## Do not assume

* Do not assume reminder content or UI placement.
* Do not assume this is a defect rather than a feature request.

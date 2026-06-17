# BUG-20260614-divine-smite-manual-modal

* status: inbox
* severity: S3
* priority: P2
* reported date: 2026-06-14
* reported by: developer
* area: Weapon Resolution / Divine Smite / Manual Mode
* confidence: medium

## Summary

The weapon resolution modal should support non-automation mode for Divine Smite, with fields for manual Divine Smite damage.

## User-visible impact

Players may not be able to conveniently add Divine Smite damage when using a manual/non-automated resolution flow.

## Observed behavior

The uploaded debugging notes say: "non automation mode for divine smite so the weapon resolution modal has spots for divine smite damage."

## Expected behavior
Weapon resolution should allow a manual Divine Smite damage entry path when automation is disabled or not desired.

## Surface clarification needed
This is a UI capability request for the weapon resolution modal. It needs to be clarified which surface (/dm, /dmcontrol, or /lan) is the priority for this manual override.

## Reproduction steps
Unknown.


## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Character/class using Divine Smite.
* Surface used.
* Screenshot or description of current weapon resolution modal.
* Desired fields and damage types.
* Whether spell slot/resource spending should be automatic or manual.

## Suspected areas / hypotheses

* Weapon resolution modal UI.
* Manual damage entry flow.
* Divine Smite resource/damage integration.
* Do not treat this as root cause.

## Related history

The same debugging report mentions weapon attack/reload failures, but this report tracks a modal capability request only.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this belongs in backlog, evidence capture, Gemini task, Codex task, or smoke coverage.

## Do not assume

* Do not assume desired automation behavior.
* Do not assume this blocks all weapon attacks.

# BUG-20260614-enemy-name-generator-yaml-subnames

## Triage Disposition

- **Status**: Triaged backlog/design
- **Triage Date**: 2026-06-26
- **Disposition**: Data-model/product design clarification before app work.
- **Reason**: Desired YAML schema and ID behavior need examples.

* status: inbox
* severity: S3
* priority: P2
* reported date: 2026-06-14
* reported by: developer
* area: Enemy Data / Name Generation
* confidence: medium-low

## Summary

Enemy name generator lists should be tied to YAMLs with subname for ID.

## User-visible impact

Enemy names/IDs may be less useful or less stable than desired, making it harder for the DM to distinguish generated enemies.

## Observed behavior

The uploaded debugging notes say: "enemny name generator lists tied to yamls with subname for ID."

## Expected behavior
Enemy name generator behavior should support YAML-tied lists and subnames for stable/useful enemy IDs, subject to product design.

## Surface clarification needed
This is a feature/data-model request for enemy generation. Developer decision is needed on the desired YAML schema for subnames and how they should be used for ID stability.

## Reproduction steps
Unknown.


## Environment

Unknown.

## Evidence provided

Developer note only.

## Missing evidence

* Example enemy YAML.
* Current generated name/ID.
* Desired generated name/ID.
* Whether this is a bug in existing behavior or a feature/data model request.

## Suspected areas / hypotheses

* Enemy YAML schema.
* Enemy name generation.
* Encounter/enemy ID display.
* Do not treat this as root cause.

## Related history

None provided.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this belongs in backlog/data design, evidence capture, Gemini task, Codex task, or smoke coverage.

## Do not assume

* Do not assume desired YAML schema.
* Do not assume existing generated names are currently broken without examples.

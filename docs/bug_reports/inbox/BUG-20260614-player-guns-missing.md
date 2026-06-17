# BUG-20260614-player-guns-missing

- status: inbox
- severity: S3
- priority: P2
- reported date: 2026-06-14
- reported by: developer
- area: Inventory / Equipment / Player Actions
- confidence: medium

## Summary
The developer noted that guns need to be added for all players.

## User-visible impact
Players who should have firearm options may not be able to select or use the correct weapons during combat.

## Observed behavior
The uploaded debugging notes say: "add guns for all players."

## Expected behavior
All relevant player characters should have appropriate gun/firearm options available wherever weapons or attacks are selected.

## Reproduction steps
Unknown.

## Environment
Unknown. Surface not specified.

## Surface clarification needed
This report is a data/coverage request ("add guns for all players"). It should be clarified whether this is a request for new item YAMLs, or a request to update specific character `.yaml` files in `players/`.

## Evidence provided
Developer note only.

## Missing evidence
- Which characters are missing guns.
- Which gun items should be available.
- Whether the issue is missing inventory, missing equip state, or missing attack option.
- Surface used: LAN player page, `/dm`, or another surface.
- Latest console log and debug trace if attack selection is involved.

## Suspected areas / hypotheses
- Character inventory/equipment data.
- Weapon attack dropdown generation.
- Player command weapon resolution.
- Do not treat this as root cause.

## Related history
The same debugging report also mentions reload and weapon attack failures, but this report tracks only missing guns as a data/equipment coverage issue.

## Orchestrator handoff
This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this belongs in evidence capture, backlog/data cleanup, Gemini task, Codex task, or smoke coverage.

## Do not assume
- Do not assume which players should have guns.
- Do not assume the current repo data is missing guns without current context.
- Do not assume this is connected to the reload/weapon attack failure bug.

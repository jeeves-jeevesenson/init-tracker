# BUG-20260627-manage-spells-free-spell-limit-and-save-failures

- **Title / ID**: BUG-20260627-manage-spells-free-spell-limit-and-save-failures — Manage Spells blocks free spell changes and save fails for some players
- **Status**: closed / completed via work item
- **Severity**: S1
- **Priority**: P1
- **Reported date**: 2026-06-27
- **Reported by**: developer
- **Area**: LAN Player Page `/` > Manage Spells
- **Confidence**: Medium

## Summary

During testing on the player surface at `http://10.3.25.235:8787/`, the developer observed multiple Manage Spells failures.

As Eldramar, free spell handling was broken in two ways: Eldramar could not add a free spell when he had too many known or prepared spells, and Eldramar could not remove free prepared spells after adding them. Other players using the same surface but different characters, with Ctihiya named as an example, reported that saving in Manage Spells did not work at all.

## User-visible impact

Players may be unable to correctly configure spells from the player surface. Free spells may be incorrectly blocked by normal known/prepared limits, free prepared spells may become stuck after being added, and some characters may be unable to save Manage Spells changes at all.

This can block real table use because players cannot reliably prepare, add, remove, or save spells without DM intervention.

## Observed behavior

- Testing surface: `http://10.3.25.235:8787/`
- Surface type: player-facing LAN page
- Screen: Manage Spells
- Character: Eldramar
- Eldramar could not add a free spell if he had too many known or prepared spells.
- This is incorrect from the developer’s perspective because the spell is free.
- Eldramar could not remove free prepared spells after adding them.
- Other players on the same surface but different characters reported that saving did not work at all.
- Ctihiya was named as an example affected character for the save failure.

## Expected behavior

- Free spells should not be blocked by normal known/prepared limits if they are truly free.
- Free prepared spells added through Manage Spells should be removable through Manage Spells.
- Manage Spells save should work for all valid player characters on the player surface.
- Saved changes should persist and be reflected in the character state after save/refresh.

## Reproduction steps

1. Open `http://10.3.25.235:8787/`.
2. Select or act as Eldramar.
3. Open Manage Spells.
4. Put Eldramar into a state where known or prepared spell limits are exceeded.
5. Attempt to add a free spell.
6. Observe that the add is blocked.
7. Add a free prepared spell if possible.
8. Attempt to remove that free prepared spell.
9. Observe that removal fails or does not persist.
10. Select another character, such as Ctihiya.
11. Open Manage Spells.
12. Make a valid spell-management change.
13. Attempt to save.
14. Observe that saving reportedly does not work.

## Environment

- Environment: testing
- Surface URL: `http://10.3.25.235:8787/`
- Surface: LAN Player Page `/`
- Characters observed/reported: Eldramar, Ctihiya
- Browser/client: unknown
- Backend commit/state: unknown
- Local vs production scope: unknown

## Evidence provided

- Developer observation from testing.
- Exact player surface URL provided.
- Eldramar identified as directly affected by free spell add/remove failures.
- Ctihiya identified as an example affected character for save failure.
- Failure context identified as Manage Spells.

## Missing evidence

- Name of the free spell Eldramar attempted to add.
- Name or names of the free prepared spells Eldramar could not remove.
- Exact known/prepared counts before the blocked add.
- Whether the UI showed an error, disabled a button, silently refused, or reverted after refresh.
- Whether save failure produced a visible message, spinner, no-op, stale refresh, or rollback.
- Browser console text from Eldramar’s browser during add/remove attempts.
- Browser console text from Ctihiya or another affected player during save failure.
- Latest backend console log covering the attempts.
- Latest debug trace or runtime report covering the session.
- Whether this reproduces locally, only on the LAN testing host, or across deployments.

## Evidence commands to run

From repo root:

- `scripts/chatgpt_context_refresher.sh`
- `cat /tmp/init-tracker-context-refresher.txt`
- `git status --short`
- `git log --oneline -5`
- `ls -lt logs | head -40`
- `LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"`
- `TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"`
- `grep -Rni "Eldramar\|Ctihiya\|Manage Spells\|free spell\|prepared\|known\|save" logs docs/runtime_reports 2>/dev/null | tail -120`

Also capture browser console errors from the affected player browsers during the failed Manage Spells actions.

## Suspected areas / hypotheses

- Hypothesis only: Manage Spells may be applying normal known/prepared caps before checking whether a spell is free.
- Hypothesis only: Free prepared spells may be missing a valid remove/unprepare path.
- Hypothesis only: Manage Spells save may fail for specific character data shapes or player identity/character selection cases.
- Hypothesis only: The UI and backend may disagree about free spell metadata or save payload validity.

## Related history

These failures were reported together from the same testing context and the same player-facing Manage Spells surface. They may share a cause, but that should not be assumed without current evidence.

## Orchestrator handoff

This bug was promoted into `docs/work_items/current_work.md`, repaired, browser-smoked by the developer, and closed. Orchestrator should read this bug report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, a smoke test, or backlog.

## Do not assume

- Do not assume root cause.
- Do not assume current repo state, current gate status, deployment topology, service names, ports beyond the developer-provided URL, or commit.
- Do not assume all characters are affected.
- Do not assume Eldramar’s free spell failures and Ctihiya’s save failure have the same cause.
- Do not assume whether the failure is frontend-only, backend-only, command-contract-related, authorization-related, or character-data-related.


## Closeout

Closed on 2026-06-27 via `docs/work_items/completed/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md`.

Developer browser smoke passed after scoped repair:
- Eldramar free spell add/prepare behavior works at/over normal cap.
- Eldramar free prepared spell remove/unprepare behavior works.
- Ctihiya / стихия Manage Spells save persists across reload.
- Normal non-free spell limit behavior remains enforced.

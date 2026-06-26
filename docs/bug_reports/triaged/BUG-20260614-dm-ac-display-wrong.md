# BUG-20260614-dm-ac-display-wrong

## Triage Disposition

- **Status**: Triaged unresolved
- **Triage Date**: 2026-06-26
- **Disposition**: Evidence capture candidate.
- **Reason**: DM-facing AC display can affect tactical decisions, but specific combatants/expected values are missing.

- status: inbox
- severity: S2
- priority: P1
- reported date: 2026-06-14
- reported by: developer
- area: DM Cockpit / Roster / Character Stats
- confidence: medium

## Summary
AC does not show properly on `/dm`.

## User-visible impact
The DM may make incorrect tactical decisions if armor class is missing, stale, or displayed incorrectly.

## Observed behavior
The uploaded debugging notes say: "ac doesnt show properly on /dm."

## Expected behavior
The `/dm` surface should show the correct AC for relevant characters and enemies.

## Reproduction steps
1. Open `/dm`.
2. View combatants or roster entries with AC values.
3. Compare displayed AC with the expected character/enemy AC.

## Environment
Surface: `/dm`.
Other environment details unknown.

## Evidence provided
Developer note only.

## Missing evidence
- Screenshot of the wrong AC display.
- Which combatant(s) show incorrect AC.
- Expected AC vs actual displayed AC.
- Browser console errors from `/dm`.
- Latest backend console log and debug trace summary.

## Evidence commands to run
```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
```

## Suspected areas / hypotheses

* `/dm` display rendering.
* Backend combatant serialization.
* Character/enemy stat source used by DM cockpit.
* Do not treat this as root cause.

## Related history

None provided.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume whether AC is wrong for players, enemies, or both.
* Do not assume current commit, dirty state, or root cause.

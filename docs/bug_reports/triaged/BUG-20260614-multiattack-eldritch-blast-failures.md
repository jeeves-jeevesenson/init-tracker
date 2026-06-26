# BUG-20260614-multiattack-eldritch-blast-failures

## Triage Disposition

- **Status**: Triaged unresolved
- **Triage Date**: 2026-06-26
- **Disposition**: Evidence capture candidate.
- **Reason**: Attack-resolution failures are core combat blockers and may force manual HP/troop cleanup.

* status: inbox
* severity: S1
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Attacks / Multiattack / Player Actions
* confidence: medium-low

## Summary

Multiattack is producing errors, and Eldritch Blast may be broken in the same general attack-resolution area.

## User-visible impact

Combat automation becomes unreliable, requiring manual HP adjustments and manual troop removal.

## Observed behavior

The uploaded debugging notes say:

* "strange multiattack error, i need to adjust hp and remove troops manually because of this"
* "Eldtrich blast is broken and maybe multiattack"

## Expected behavior

Multiattack and Eldritch Blast should resolve attacks and damage cleanly without forcing manual correction.

## Reproduction steps

Unknown. Likely:

1. Trigger a multiattack action or Eldritch Blast cast.
2. Resolve targets/damage.
3. Observe error and resulting HP/troop state.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Actor using multiattack.
* Target(s).
* Exact error text.
* Whether Eldritch Blast fails on attack roll, damage roll, target selection, or log/rendering.
* Browser console output.
* Backend console log and debug trace around the failure.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "multiattack\|eldritch\|blast\|attack" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* Attack resolution.
* Multiattack action expansion.
* Spell attack handling for Eldritch Blast.
* Damage application and enemy removal after failed resolution.
* Do not treat this as root cause.

## Related fixed player-surface work
- **Resolved**: [BUG-20260614-player-spell-slots-not-syncing](../../work_items/active/BUG-20260614-player-spell-slots-not-syncing.md) (Completed 2026-06-14)
- **Note**: Eldritch Blast failures can sometimes be caused by UI/resource desync if the client thinks it has slots/resources but the backend disagrees (or vice versa). A player-surface sync fix was applied on 2026-06-14. This report remains active for broader attack-resolution errors or DM-surface desync.

## Related history

May be related to weapon attack failures and manual HP cleanup, but this should remain a separate report until evidence connects them.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume Eldritch Blast and multiattack share root cause.
* Do not assume which surface was used.

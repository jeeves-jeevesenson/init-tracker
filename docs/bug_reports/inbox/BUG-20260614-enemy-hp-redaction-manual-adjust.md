# BUG-20260614-enemy-hp-redaction-manual-adjust

* status: inbox
* severity: S2
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Logs / HP Privacy / DM Manual Adjust
* confidence: medium

## Summary

Enemy HP should be redacted in logs when the DM manually adjusts HP.

## User-visible impact

Player-facing logs may reveal hidden enemy HP information after DM manual adjustments.

## Observed behavior

The uploaded debugging notes say: "enemy HP redaction in logs when dm manually adjusts."

## Expected behavior

When the DM manually adjusts enemy HP, logs shown outside the DM-only context should redact hidden enemy HP as intended.

## Reproduction steps

1. Use `/dm` to manually adjust enemy HP.
2. Inspect combat/event logs visible to players and DM.
3. Confirm whether enemy HP values are exposed where they should be hidden.

## Environment

Surface: `/dm` for manual adjustment.
Log visibility scope unknown.

## Evidence provided

Developer note only.

## Missing evidence

* Example log line leaking enemy HP.
* Whether leak is player-facing, DM-facing, or both.
* Enemy type/name.
* Current privacy/redaction expectation.
* Latest backend logs around manual adjustment.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
grep -Rni "manual\|adjust\|hp\|HP" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* Manual HP adjustment logging.
* Player-facing vs DM-facing log channel separation.
* HP redaction policy.
* Do not treat this as root cause.

## Related history

Related to the separate bug where enemies can remain at 0 HP after DM override.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume all logs should redact HP; DM-only logs may intentionally show it.
* Do not assume the leak is currently reproducible without current logs.

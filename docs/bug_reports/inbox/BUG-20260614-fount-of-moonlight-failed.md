# BUG-20260614-fount-of-moonlight-failed

* status: inbox
* severity: S1
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Spells / Player Actions
* confidence: low

## Summary

Fount of Moonlight failed during use.

## User-visible impact

A spell or magical feature may not resolve correctly during combat, blocking expected player actions.

## Observed behavior

The uploaded debugging notes say: "fount of moonlight failed."

## Expected behavior

Fount of Moonlight should execute according to its configured rules and update combat state/logs consistently.

## Reproduction steps

Unknown.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Character using Fount of Moonlight.
* Surface used.
* Whether failure happened at selection, cast, targeting, damage, effect application, resource consumption, or logging.
* Expected resource/slot behavior.
* Actual browser/backend error text.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "fount\|moonlight" logs docs/runtime_reports 2>/dev/null | tail -80
```

## Suspected areas / hypotheses

* Spell catalog/configuration.
* Spell action execution.
* Effect/resource application.
* Do not treat this as root cause.

## Related history

The debugging report also mentions Moonbeam in the Counterspell example, but no direct connection is established.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume spell name spelling/configuration without current data.
* Do not assume resource changes occurred unless logs confirm.

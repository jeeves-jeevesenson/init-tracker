# BUG-20260614-reactions-hold-combat

* status: inbox
* severity: S1
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Reactions / Turn Flow
* confidence: medium-low

## Summary

Reactions are buggy and can hold up combat.

## User-visible impact

Combat flow can stall while the table waits for reaction prompts or resolution, forcing manual intervention or delaying turns.

## Observed behavior

The uploaded debugging notes say: "reactions are kind of buggy, and can hold up combat."

## Expected behavior

Reaction prompts should appear only when valid, resolve cleanly, and not block combat indefinitely.

## Reproduction steps

Unknown.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Specific reaction involved.
* Actor and triggering action.
* Whether prompt appeared, failed to appear, or could not be dismissed.
* Approximate delay/stall behavior.
* Whether repeated clicks made it worse.
* Browser console, backend log, and debug trace summary.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "reaction\|counterspell\|opportunity" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* Reaction queue/lifecycle.
* UI blocking state.
* Turn advancement gating.
* Do not treat this as root cause.

## Related fixed player-surface work
- **Resolved**: [BUG-20260614-player-mount-lockout](../../work_items/completed/BUG-20260614-player-mount-lockout.md)
- **Note**: The `mount_response` was exempted from the turn-gate blocker on 2026-06-17 to prevent combat stalls during mounting. If other reactions (Counterspell, Opportunity Attacks) still hold up combat, this report remains active for those triggers.

## Related history

Related notes include Counterspell ally trigger behavior and end-turn reminders.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume all reactions are broken.
* Do not assume this is the same bug as Counterspell not triggering.

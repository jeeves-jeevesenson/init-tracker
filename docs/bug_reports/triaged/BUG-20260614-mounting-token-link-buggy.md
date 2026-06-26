# BUG-20260614-mounting-token-link-buggy

## Triage Disposition

- **Status**: Triaged unresolved
- **Triage Date**: 2026-06-26
- **Disposition**: Evidence capture candidate, distinct from completed mount-lockout bug.
- **Reason**: Completed mount-lockout work did not close intermittent rider-follow/token-link desync.

* status: inbox
* severity: S2
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Map / Tokens / Mounting
* confidence: medium

## Summary

Mounting is unreliable. Sometimes it works, but sometimes the bottom token can move while the top token is left behind.

## User-visible impact

Mounted movement becomes unreliable on the tactical map, forcing manual token correction and risking incorrect positioning.

## Observed behavior

The uploaded debugging notes say: "mounting isnt working, the person who is the bottom can move and the person on top gets left behind. actually mounting is just buggy sometimes it works sometimes it doesnt."

## Expected behavior

When two tokens are mounted/linked, movement of the bottom/mount token should preserve the mounted relationship and move the top/rider token as intended.

## Reproduction steps

1. Place two tokens in a mounting relationship.
2. Move the bottom/mount token.
3. Observe whether the top/rider token follows.
4. Repeat multiple times to check intermittent behavior.

## Environment

Surface unknown; likely map-related.
Need confirm whether `/dm`, `/dm/map`, or `/dmcontrol` was used.

## Evidence provided

Developer note only.

## Missing evidence

* Surface used.
* Token names.
* Whether grid and tokens were visible.
* Whether drag/drop or another move command was used.
* Browser console errors.
* Latest backend console log and debug trace summary.
* Local vs production scope.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "mount\|mounted\|token\|move" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* Token link/mount state.
* Map movement synchronization.
* Drag/drop move handling.
* Do not treat this as root cause.

## Related fixed player-surface work
- **Resolved**: [BUG-20260614-player-mount-lockout](../../work_items/completed/BUG-20260614-player-mount-lockout.md)
- **Note**: A major player-surface mount lockout caused by turn-gate blockers was fixed on 2026-06-17. During that fix, the "rider-follow desync" (leaving token behind) was not reproduced and server broadcasts were verified as synchronized. However, if this intermittent desync persists on `/dm` or `/dmcontrol`, it remains an open issue.

## Related history

None provided.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume which map surface is affected.
* Do not assume this is only a UI bug; backend token state may need evidence.

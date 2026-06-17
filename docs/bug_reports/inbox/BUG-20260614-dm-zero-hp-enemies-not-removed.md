# BUG-20260614-dm-zero-hp-enemies-not-removed

* status: inbox
* severity: S1
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: DM Cockpit / HP Override / Enemy Removal
* confidence: medium

## Summary

Enemies can remain at 0 HP when the DM manually overrides HP in `/dm`, instead of being removed from combat.

## User-visible impact

The DM must manually clean up defeated enemies, slowing combat and risking stale/incorrect encounter state.

## Observed behavior

The uploaded debugging notes say: "enemies can be at 0 hp when the dm ovverides in /dm instead of being removed."

## Expected behavior

When a DM override reduces an enemy to 0 HP, the enemy should follow the intended defeated/removal flow.

## Reproduction steps

1. Open `/dm`.
2. Select or edit an enemy.
3. Manually override HP to 0.
4. Observe whether the enemy remains active instead of being removed.

## Environment

Surface: `/dm`.
Other environment details unknown.

## Evidence provided

Developer note only.

## Missing evidence

* Enemy name/type.
* Whether this happens for all enemies or only specific troops.
* Whether the enemy remains visible on map, initiative, logs, or all surfaces.
* Latest console log and debug trace around the HP override.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "override\|hp\|defeated\|remove" logs docs/runtime_reports 2>/dev/null | tail -80
```

## Suspected areas / hypotheses

* Manual HP override flow.
* Enemy defeated/removal rules.
* Combat state synchronization after manual edits.
* Do not treat this as root cause.

## Related history

The developer also reported needing to manually adjust HP and remove troops after multiattack errors.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume 0 HP should always auto-delete rather than enter a defeated state.
* Do not assume this shares root cause with multiattack failures.

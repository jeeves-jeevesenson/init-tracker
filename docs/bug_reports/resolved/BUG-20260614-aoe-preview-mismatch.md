# BUG-20260614-aoe-preview-mismatch

* status: resolved (already fixed/stale)
* resolution: Already fixed by BUG-20260614-player-fireball-preview-applies-one-target.
* resolution date: 2026-06-17
* severity: S1
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Spells / AoE Preview / Targeting
* confidence: high

## Summary

The AoE enemy preview does not match the real spell effect. The preview showed two enemies in range, but the actual spell roll affected only one.

## User-visible impact

The DM/player may choose spell placement based on incorrect target previews, leading to wrong tactical outcomes and loss of trust in the map/spell UI.

## Observed behavior

The uploaded debugging notes say: "the aoe enemy preview does not match real spell effects. the aoe preview showed 2 in range and actually only had 1 when stuff was rolled."

## Expected behavior

AoE preview target count should match the actual targets used when the spell is rolled/resolved.

## Reproduction steps

1. Place an AoE spell preview over enemies.
2. Observe displayed enemies in range.
3. Resolve/roll the spell.
4. Compare previewed targets with actual affected targets.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Spell used.
* Surface used.
* Map/grid visibility and token positions.
* Screenshot of preview before roll.
* Combat log after roll.
* Browser console errors.
* Latest backend console log and debug trace summary.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "aoe\|preview\|range\|target\|spell" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* AoE preview geometry.
* Backend spell target calculation.
* Coordinate/grid mismatch between preview and resolution.
* Do not treat this as root cause.

## Related fixed player-surface work
- **Resolved**: [BUG-20260614-player-fireball-preview-applies-one-target](../../work_items/completed/BUG-20260614-player-fireball-preview-applies-one-target.md)
- **Note**: The player-surface Fireball preview mismatch (radius loss and coordinate offset) was fixed on 2026-06-16. This included fixes to `spell_engine_primitives.py` and `assets/web/lan/index.html`. However, the DM control surface (`assets/web/dmcontrol/index.html`) still uses the old point-sampling math and may still exhibit this mismatch. DM-surface behavior is not proven fixed.

## Related history

The debugging report also includes Fireball damage inconsistency. That is tracked separately because preview targeting and damage rolling may be distinct issues.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume the preview or backend is wrong without comparing current geometry and logs.
* Do not assume this affects every AoE spell.

# BUG-20260614-fireball-damage-roll-inconsistent

* status: resolved
* severity: S2
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Spells / Damage Resolution
* confidence: high

## Resolution Summary

- **Implementation Task**: BUG-20260617-fireball-shared-damage-roll-impl-01
- **Fix**: Refactored `_lan_auto_resolve_cast_aoe` in `dnd_initative_tracker.py` to pre-calculate damage rolls for each structural spell effect before iterating over targets. Caching by formula ensures that success/fail outcomes share the same base roll.
- **Verification**: New unit test `tests/test_fireball_shared_damage.py` confirms shared rolls across multiple targets (including save success/failure).
- **Smoke Evidence**: Developer browser smoke passed on 2026-06-17.
- **Smoke Log**: `logs/smoke/BUG-20260614-fireball-damage-roll-inconsistent_smoke-server_20260617-154407.log`
- **Debug Trace**: `logs/debug-trace-20260617-154407.jsonl`

## Summary

Fireball damage appears to be rolled separately per target instead of rolling damage once and applying that roll to all affected targets with save outcomes.

## User-visible impact

Area damage can be inconsistent with expected D&D 2024 damage-roll behavior, affecting combat balance and trust in automation.

## Observed behavior

The uploaded debugging notes include this log excerpt:

* `21:42:51 Fireball: Black and Tan Rifleman 2 save DEX PASS (25 vs DC 18) -> 12 damage (12 Fire)`
* `21:42:51 Fireball: Black and Tan Rifleman 3 save DEX FAIL (7 vs DC 18) -> 21 damage (21 Fire)`
* `21:42:51 Fireball: Black and Tan Lieutenant 1 save DEX FAIL (14 vs DC 18) -> 32 damage (32 Fire)`

The developer notes: "damage is inconsistent, it shoudl be damage rolled once and applied to them all as per dnd 2024 damage rolls."

## Expected behavior

Fireball should roll damage once for the spell effect, then apply full or reduced damage to each target based on its saving throw.

## Reproduction steps

1. Cast Fireball against multiple targets.
2. Resolve saves.
3. Inspect combat log damage values for each target.
4. Confirm whether a single damage roll is shared across all targets.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer-provided combat log excerpt from 21:42:51.

## Missing evidence

* Character who cast Fireball.
* Surface used.
* Whether this only affects Fireball or all AoE spells.
* Latest backend logs/debug trace around the cast.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "Fireball\|damage roll\|DEX PASS\|DEX FAIL" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* AoE spell damage roll generation.
* Per-target save/damage application.
* Combat log formatting.
* Do not treat this as root cause.

## Related history

The same debugging report also says the AoE enemy preview did not match actual spell effects.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume all AoE spells are affected until tested.
* Do not assume the displayed log is the only place damage differs.

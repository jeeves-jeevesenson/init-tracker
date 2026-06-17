# BUG-20260614-counterspell-ally-trigger-missing

* status: inbox
* severity: S2
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Reactions / Spells
* confidence: medium

## Summary

Counterspell should trigger as an available reaction when an ally casts a spell, but this trigger appears missing.

## User-visible impact

Reaction automation is incomplete or incorrect, and players may miss legal reaction opportunities during spellcasting.

## Observed behavior

The uploaded debugging notes say: "counterspell should trigger for an ally if an ally is casting. like if dorian casts moonbeam."

## Expected behavior

When an ally casts a qualifying spell such as Dorian casting Moonbeam, Counterspell-capable characters should be offered the appropriate reaction opportunity if rules/config allow it.

## Reproduction steps

1. Use Dorian or another ally to cast Moonbeam.
2. Observe reaction prompts for characters with Counterspell.
3. Verify whether Counterspell appears as a valid reaction opportunity.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Character who should have Counterspell.
* Whether the Counterspell caster is allied with Dorian.
* Surface used.
* Whether reaction prompts appeared at all.
* Browser console and backend logs.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "counterspell\|reaction\|moonbeam\|dorian" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* Reaction opportunity generation.
* Spell cast event classification.
* Ally/enemy relationship checks.
* Do not treat this as root cause.

## Related history

The developer separately noted that reactions are buggy and can hold up combat.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume the current reaction implementation intentionally excludes ally casts.
* Do not assume Dorian or Counterspell data is current.

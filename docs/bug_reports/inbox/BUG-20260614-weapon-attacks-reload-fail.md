# BUG-20260614-weapon-attacks-reload-fail

* status: inbox
* severity: S1
* priority: P1
* reported date: 2026-06-14
* reported by: developer
* area: Inventory / Weapons / Player Actions
* confidence: medium

## Summary

Reloading appears unreliable, and a saber attack also failed, suggesting a broader weapon action failure rather than only a firearm reload bug.

## User-visible impact

Players may be unable to reliably make weapon attacks, which blocks core combat flow.

## Observed behavior

The uploaded debugging notes say:

* "reloading doesnt really work. you can select it and my weapon shows loaded but no way for me to reload"
* "scratch that a saber attack failed too"

## Expected behavior

Reload actions should be available and should update weapon load state correctly. Saber attacks and other weapon attacks should resolve successfully.

## Reproduction steps

1. Use a character with a reloadable weapon.
2. Attempt to reload after selecting the reload action or weapon.
3. Observe whether the UI provides a way to reload and whether load state changes.
4. Attempt a saber attack.
5. Observe whether the attack resolves.

## Environment

Unknown. Surface not specified.

## Evidence provided

Developer note only.

## Missing evidence

* Character name.
* Weapon name(s).
* Whether weapon was equipped.
* Selected attack/action.
* Actual error or failed output.
* Browser console text.
* Backend logs showing weapon resolution.

## Evidence commands to run

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "reload\|loaded\|saber\|weapon" logs docs/runtime_reports 2>/dev/null | tail -120
```

## Suspected areas / hypotheses

* Weapon equip/load state.
* Player action contract for reload/attack.
* Weapon attack resolution modal.
* Do not treat this as root cause.

## Related history

The debugging report separately asks to add guns for all players and mentions manual Divine Smite support in weapon resolution.

## Orchestrator handoff

This bug is not active work until promoted into `docs/work_items/current_work.md` or an active work item. Orchestrator should read this report, request current context if needed, classify it against active work/recovery gates, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test.

## Do not assume

* Do not assume reload and saber failure share root cause.
* Do not assume weapon data is current without context.

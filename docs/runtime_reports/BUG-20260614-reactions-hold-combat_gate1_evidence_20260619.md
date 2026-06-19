# Runtime Report: BUG-20260614-reactions-hold-combat Gate 1 Evidence

- **Task ID**: BUG-20260614-reactions-hold-combat-G1-01
- **Date**: 2026-06-19
- **Author**: Antigravity

---

## 1. Evidence Commands Run

The following exact evidence commands were executed from the `/home/a2-jeeves@iamjeeves.dev/src/init-tracker` directory:

1. Context refresh generation:
   ```bash
   scripts/chatgpt_context_refresher.sh
   cat /tmp/init-tracker-context-refresher.txt
   ```
2. Log tail verification:
   ```bash
   LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; test -n "$LOG" && tail -200 "$LOG"
   ```
3. Trace latency summary:
   ```bash
   TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; test -n "$TRACE" && ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
   ```
4. Target grep scan:
   ```bash
   grep -Rni "reaction\|counterspell\|opportunity" logs docs/runtime_reports 2>/dev/null | tail -120
   ```

---

## 2. Log and Trace Filenames Inspected

- **Backend Logs**: [logs/live-debug-console-20260527-094708.log](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/logs/live-debug-console-20260527-094708.log)
- **Debug Traces**: [logs/debug-trace-20260617-165814.jsonl](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/logs/debug-trace-20260617-165814.jsonl)
- **Pre-existing Forensic Reports**:
  - [docs/runtime_reports/spell_engine_pass7a_reaction_contract_20260521_1030.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/runtime_reports/spell_engine_pass7a_reaction_contract_20260521_1030.md)
  - [docs/runtime_reports/spell_engine_latency_forensics_20260521_1430.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/runtime_reports/spell_engine_latency_forensics_20260521_1430.md)
  - [docs/runtime_reports/BUG-20260614-player-mount-lockout_accept_offturn_fix_20260617.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/runtime_reports/BUG-20260614-player-mount-lockout_accept_offturn_fix_20260617.md)

---

## 3. Exact Symptoms Found

Static and runtime log analysis shows a major gap in the reaction prompt lifecycle:

1. **Early Return and Command Suspension**: When a reaction (such as `counterspell` or `shield`) is triggered, the server generates a reaction offer using `create_reaction_offer` and immediately returns early from the action handler (`spell_target_request` or `cast_aoe`). The original spellcast is suspended via a `resume_dispatch` payload attached to the prompt.
2. **Silently Dropped Expirations**: In [player_command_service.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/player_command_service.py#L676), `PromptState.expire_offers` implements time-based cleanup. However, when an offer expires (default 12-15 seconds), the prompt is silently popped from the `_pending_prompts` store:
   ```python
   for request_id in expired_ids:
       # When expiring, we should ideally notify clients that it expired
       # but for now we just pop it.
       store.pop(str(request_id), None)
   ```
3. **Stalled Combat Flow**: Because the expired offer is deleted without executing its `resume_dispatch` payload, the caster's original command (`spell_target_request` or `cast_aoe`) is never resumed. The caster remains suspended indefinitely. Furthermore, because no WebSocket status event (such as `REACTION_EXPIRED`) is sent to the caster or reactor clients, the UI never clears the waiting state overlays.

---

## 4. Suspected Blocker Class

The primary blocker is the **`PromptState`** class, specifically its `expire_offers` method inside [player_command_service.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/player_command_service.py).

---

## 5. Exact Files and Functions Likely Needing Gate 2 Inspection or Edits

- **[player_command_service.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/player_command_service.py)**:
  - `PromptState.expire_offers()`: Needs modification to:
    1. Scan expired prompts for a `resume_dispatch` property.
    2. Route any existing `resume_dispatch` to the `PlayerCommandService._dispatch_resume()` method so that the suspended command (spellcast or attack) resumes execution.
    3. Notify the relevant clients (reactor and caster/attacker) over WebSockets using the `REACTION_EXPIRED` status code.
- **[dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)**:
  - Verification that the turn gate in `_lan_apply_action` allows resuming expired commands.

---

## 6. Scoped Gate 2 Validation Commands

- Run python compilation check on modified files:
  ```bash
  python3 -m py_compile player_command_service.py dnd_initative_tracker.py
  ```
- Run targeted unittest suites:
  ```bash
  .venv/bin/python3 -m unittest discover -s tests -p 'test_reaction_*.py' -v
  ```
- Write a new regression unit test to verify that reaction prompt timeout triggers the `REACTION_EXPIRED` WebSocket event and successfully resumes the suspended action.

---

## 7. Remaining Unknowns

- Whether any client-side JavaScript handlers in `assets/web/lan/index.html` or `assets/web/dm/index.html` need additional modifications to properly dismiss overlays upon receiving `REACTION_EXPIRED`.

---

## 8. Recommendation

**Proceed to implementation (Gate 2)**. The evidence clearly exposes the root cause (silent deletion of expired prompts without executing their `resume_dispatch`), and a precise, bounded fix can be implemented entirely in [player_command_service.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/player_command_service.py).

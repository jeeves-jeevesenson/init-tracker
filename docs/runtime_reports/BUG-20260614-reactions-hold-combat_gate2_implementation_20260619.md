# Runtime Report: BUG-20260614-reactions-hold-combat Gate 2 Implementation

- **Task ID**: BUG-20260614-reactions-hold-combat-G2-01
- **Date**: 2026-06-19
- **Author**: Antigravity

---

## 1. Root Cause Recap

Before the fix, when a reaction prompt (such as `counterspell` or `shield`) was triggered:
1. The server generated a pending reaction offer and returned early, suspending the triggering action (e.g. `spell_target_request` or `cast_aoe`). The suspended action's payload was stored in a `resume_dispatch` property on the prompt.
2. If the prompt reached its timeout (expired), `PromptState.expire_offers()` silently popped/deleted the prompt from the internal store without executing the associated `resume_dispatch` payload or notifying the websocket clients.
3. This left the active caster/attacker's action suspended indefinitely, causing combat rounds to stall permanently. Caster and reactor client UIs remained stuck in a "Waiting..." modal/overlay.

---

## 2. Exact Files and Functions Changed

- **[player_command_service.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/player_command_service.py)**:
  - `PromptState.expire_offers()`: Rewritten to safely handle expired prompts:
    - Retreives each expired prompt's reactor CID and `resume_dispatch` payload.
    - Routes the prompt to `PlayerCommandService._resolve_reaction_response(choice="decline")` to authoritatively resolve it off-turn, updating trigger-specific flags (e.g., `_counterspell_resolution_done = True`).
    - Ensures the prompt is popped/deleted from the store.
    - Sends the `REACTION_EXPIRED` websocket result to all relevant clients (both the reactor's connections and the caster/attacker's connection).
    - Resumes the suspended action using the safe `PlayerCommandService._dispatch_resume()` path.
- **[tests/test_reaction_prompt_expiry_resume.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_reaction_prompt_expiry_resume.py)** (new file):
  - Added a regression test validating that prompt timeout triggers `REACTION_EXPIRED` websocket events for all parties and successfully resumes the suspended action with appropriate resolution flags.

---

## 3. Timeout Behavior After Fix

Upon prompt timeout:
1. The prompt is authoritatively resolved as `"decline"`, which updates resolution flags (such as `_counterspell_resolution_done`).
2. The prompt is popped from the store, preventing any duplicate evaluation or memory leaks.
3. The suspended action (e.g., spellcast or attack) is safely resumed off-turn under the same execution path as an explicit player Decline.
4. The action executes to completion (e.g. spell proceeds to target resolution because it was not countered).

---

## 4. Client Notification Behavior After Fix

The server now broadcasts a structured `reaction_result` payload with status `REACTION_EXPIRED` to:
- The reactor's client websocket(s), allowing their UI to clear the pending reaction decision modal.
- The caster/attacker's websocket, allowing their UI to clear the "Waiting for response..." status toast or overlay.

---

## 5. Validation Commands and Pass/Fail

All validation checks passed successfully from the `/home/a2-jeeves@iamjeeves.dev/src/init-tracker` directory:

1. **Compilation Check**:
   - Command: `./.venv/bin/python3 -m py_compile player_command_service.py`
   - Result: **Pass** (Exit Code 0, no warnings)
2. **Targeted Regression Unittest**:
   - Command: `./.venv/bin/python3 -m unittest tests.test_reaction_prompt_expiry_resume`
   - Result: **Pass** (1 test run, 0 errors, 0 failures)
3. **Workspace Whitespace Check**:
   - Command: `timeout 10s git diff --check`
   - Result: **Pass** (No whitespace errors)

---

## 6. Developer Browser Smoke Requirement

**Yes, developer-led browser smoke testing is still required.**
While backend execution and websocket broadcasts have been fully verified under unit testing, the developer must verify that:
1. The UI assets (`assets/web/lan/index.html` and `assets/web/dm/index.html`) correctly parse the `REACTION_EXPIRED` message type.
2. The waiting overlay/modal is visually cleared on both the player LAN surface and the DM operator console upon expiration.

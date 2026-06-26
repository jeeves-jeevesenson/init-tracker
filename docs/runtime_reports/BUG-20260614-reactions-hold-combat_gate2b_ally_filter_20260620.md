# Runtime Report: BUG-20260614-reactions-hold-combat Gate 2B Ally Filter

- **Task ID**: BUG-20260614-reactions-hold-combat-G2B-01
- **Date**: 2026-06-20
- **Author**: Antigravity

---

## 1. Root Cause Analysis & Fix

The developer's smoke test for Gate 2 identified that allied PCs were able to prompt and execute Counterspell (and other hostile/oppositional reactions) against each other. Because reaction eligibility did not filter by hostility/relationship status:
1. Allied spellcasts or attacks triggered unnecessary reaction pop-ups.
2. If players interacted or ignored/timed out these allied prompts, it disrupted combat pacing and flow.

We implemented relationship/hostility checks to prevent allied reaction offers using the existing helper method `_combatants_are_hostile` on the tracker:

1. **Counterspell Eligibility:**
   * File: [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)
   * Function: `_can_offer_counterspell_reaction(...)`
   * Fix: Retrieve the source combatant and return `False, "ally"` if the reactor and source are not hostile (determined by `not self._combatants_are_hostile(reactor, source)`).

2. **Spell Stopper Eligibility:**
   * File: [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)
   * Function: `_can_offer_spell_stopper_reaction(...)`
   * Fix: Retrieve the source combatant and return `False, "ally"` if the reactor and source are not hostile.

3. **Hellish Rebuke Eligibility:**
   * File: [player_command_service.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/player_command_service.py)
   * Function: `maybe_offer_hellish_rebuke(...)`
   * Fix: Immediately return `None` (preventing offer creation) if the victim and attacker are not hostile.

---

## 2. Validation Run Summary

All validation tests passed successfully from the `/home/a2-jeeves@iamjeeves.dev/src/init-tracker` directory:

1. **Compilation Check:**
   * Command: `./.venv/bin/python3 -m py_compile player_command_service.py dnd_initative_tracker.py tests/test_reaction_prompt_ally_filter.py tests/test_reaction_prompt_expiry_resume.py`
   * Result: **Pass**

2. **Existing Prompt Expiry Regression Unittests:**
   * Command: `./.venv/bin/python3 -m unittest tests.test_reaction_prompt_expiry_resume`
   * Result: **Pass (1 test run)**

3. **New Focused Faction Filter Regression Unittests:**
   * Command: `./.venv/bin/python3 -m unittest tests.test_reaction_prompt_ally_filter`
   * Result: **Pass (6 tests run)**

4. **Whitespace Compliance Check:**
   * Command: `timeout 10s git diff --check`
   * Result: **Pass**

5. **Working Tree Status:**
   * Command: `git status --short`
   * Result: Clean except for the expected modifications and the new test and report files.

---

## 3. Next Steps
* The active work item has been updated to mark Gate 2B complete.
* Proceed to developer browser smoke testing.

# BUG-20260614-reactions-hold-combat

- **Title**: Reactions can hold up combat.
- **Status**: Active
- **Source bug**: [docs/bug_reports/triaged/BUG-20260614-reactions-hold-combat.md](../../bug_reports/triaged/BUG-20260614-reactions-hold-combat.md)
- **Severity**: S1
- **Priority**: P1
- **Area**: Reactions / Turn Flow
- **Active Gate**: Gate 2B — Prevent invalid allied reaction offers while preserving expired-prompt resume behavior

## Goal

Capture enough concrete evidence to determine whether reaction prompts, reaction queue lifecycle, or turn-advancement gating can stall combat, then produce a bounded fix plan.

## User-visible impact

Combat flow can stall while the table waits for reaction prompts or resolution, forcing manual intervention or delaying turns.

## Evidence baseline

Current evidence is developer note only: reactions are buggy and can hold up combat.

## Missing evidence

- Specific reaction involved.
- Actor and triggering action.
- Whether prompt appeared, failed to appear, or could not be dismissed.
- Approximate delay/stall behavior.
- Whether repeated clicks made it worse.
- Browser console, backend log, and debug trace summary.

## Scope

### In scope

- Reaction prompt lifecycle evidence.
- Reaction queue / pending response state evidence.
- Turn advancement gating evidence.
- Related reaction triggers named by the source bug: Counterspell and Opportunity Attacks.
- Existing logs and debug trace summaries.
- Bounded fix plan after evidence.

### Out of scope

- Do not change app code in Gate 1.
- Do not change DM-side automation unless evidence identifies it as the blocker.
- Do not change monster AI.
- Do not change AoE targeting.
- Do not change mount behavior; mount lockout is already completed.
- Do not run broad/full test suites.

## Plan

### Gate 1: Evidence capture and bounded fix plan

- [x] Gather latest relevant live debug console log tail.
- [x] Gather latest debug trace latency summary.
- [x] Search only named runtime reports/logs for reaction, counterspell, and opportunity evidence.
- [x] Inspect related completed mount-lockout evidence only for turn-gate pattern comparison.
- [x] Produce a bounded fix plan with exact files likely needing edits and scoped validation commands. (See [docs/runtime_reports/BUG-20260614-reactions-hold-combat_gate1_evidence_20260619.md](../../runtime_reports/BUG-20260614-reactions-hold-combat_gate1_evidence_20260619.md))
- [x] Stop before implementation.

### Gate 2: Fix expired reaction prompts so combat resumes and clients clear waiting state

- [x] Modify `PromptState.expire_offers()` in `player_command_service.py` to route expired prompts to `_resolve_reaction_response(choice="decline")` and execute their `resume_dispatch`.
- [x] Broadcast `REACTION_EXPIRED` websocket result to reactor and caster/attacker clients upon prompt timeout.
- [x] Add focused regression unit test in `tests/test_reaction_prompt_expiry_resume.py` and verify all tests pass.
- [x] Verify no syntax or runtime warnings on edited source files.

### Gate 2B: Prevent invalid allied reaction offers

- [x] Check reactor and source/attacker hostility using `self._combatants_are_hostile(...)` helper in `_can_offer_counterspell_reaction(...)` and `_can_offer_spell_stopper_reaction(...)`.
- [x] Check victim and attacker hostility using `t._combatants_are_hostile(...)` in `maybe_offer_hellish_rebuke(...)` in `player_command_service.py`.
- [x] Add focused faction-filtering unittests in `tests/test_reaction_prompt_ally_filter.py`.

## Candidate commands

    ./.venv/bin/python3 -m py_compile player_command_service.py dnd_initative_tracker.py
    ./.venv/bin/python3 -m unittest tests.test_reaction_prompt_expiry_resume
    ./.venv/bin/python3 -m unittest tests.test_reaction_prompt_ally_filter

## Validation for Gate 2B

- `./.venv/bin/python3 -m py_compile player_command_service.py dnd_initative_tracker.py` -> Passed
- `./.venv/bin/python3 -m unittest tests.test_reaction_prompt_expiry_resume` -> Passed (1 test)
- `./.venv/bin/python3 -m unittest tests.test_reaction_prompt_ally_filter` -> Passed (6 tests)
- `git status --short` -> Checked
- `timeout 10s git diff --check` -> Passed

## Remaining Smoke Needs

- Developer-led browser smoke testing is required to verify that the player LAN and DM operator surfaces receive the `REACTION_EXPIRED` event and successfully clear all waiting modals and overlays.

## Stop condition

Stop after Gate 2B implementation and validation are complete. Do not commit or push unless explicitly asked by the developer.


## Completion Summary

- **Completion Date**: 2026-06-26
- **Final status**: Completed
- **Evidence**:
  - Gate 1 evidence report completed.
  - Gate 2 expired reaction prompt resume implementation completed.
  - Gate 2B allied reaction filter implementation completed.
  - Focused reaction regression tests passed.
  - Developer browser smoke passed after resolving the Player/LAN map drag-panning smoke blocker.
- **Smoke evidence**: `docs/runtime_reports/BUG-20260614-reactions-hold-combat_smoke_pass_20260626.md`
- **Related smoke-blocker fix**: `docs/bug_reports/resolved/BUG-20260626-player-map-drag-pan-broken.md`
- **Non-blocking follow-up**: `docs/bug_reports/inbox/BUG-20260626-aura-of-protection-grid-snap.md`

Browser smoke confirmed Dorian could cast with Eldramar present and Eldramar did not receive an allied Counterspell prompt. No reaction waiting-state stall was reported.

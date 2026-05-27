# Gate 3 Post-Patch Smoke Report — 2026-05-27

## Context

Patch under smoke:
- Task ID: ITR-20260527-G3-03
- Dirty implementation file during smoke: `dnd_initative_tracker.py`
- Trace command used post-smoke:
  - `scripts/trace_latency_summary.py logs/debug-trace-20260527-102803.jsonl`

## Product Smoke Summary

Encounter:
- All players
- 7 Black and Tan Constabulary
- Small combat session
- Long Rest tested first because it historically had the highest latency

## Results

### 1. Long Rest

Result: FAIL / P0 latency blocker.

Developer observation:
- Long Rest still took over a minute.
- This is unacceptable for table use.

Trace evidence:
- `combat_service.long_rest`: 31,364.898 ms
- top `http.request`: 31,595.198 ms
- `_load_player_yaml_cache`: 10,166.891 ms
- `_lan_snapshot`: 8,155.163 ms

Decision:
- Gate 3 remains open.
- Next latency task should focus on Long Rest root cause before further broad combat polish.

### 2. Manage Spells

Result: PASS for responsiveness and persistence, with follow-up bugs.

Developer observation:
- Manage Spells was responsive.
- Spell lists were not empty after refresh/reconnect.
- Spell casting worked.
- Bug: free spells can be added but cannot be selected for removal like prepared spells.
- Bug: switching characters can render the spell list empty until refresh. This is low production risk because players normally select their own character and stay there.

Decision:
- Do not reopen broad Gate 2.
- Track these as targeted follow-up bugs.

### 3. Wild Shape

Result: PASS for responsiveness, with mechanics bug.

Developer observation:
- Johnny's Wild Shape was responsive.
- It used the bonus action and logged correctly.
- Bug: Wild Shape resets movement to the wild-shaped form's full movement.

Expected movement rule:
- Identify distance already moved this turn.
- Remaining movement = new form speed - distance already moved.
- Minimum remaining movement is 0.

Decision:
- Responsiveness improvement is acceptable.
- Track Wild Shape movement preservation as a targeted mechanics bug.

### 4. Combat Loop

Result: IMPROVED but not production-ready.

Developer observation:
- Move, Attack, Cast, features, and End Turn are much better than prior weeks.
- The app feels pretty responsive compared to before.
- Still mildly laggy in a way that can cause user errors.
- Double-click risk remains.

Trace evidence:
- `player_command.cast_aoe`: 3,897.804 ms max observed
- `_handle_cast_aoe_request`: 3,896.947 ms max observed
- `player_command.attack_request`: 4,946.359 ms cumulative across 14 calls
- `_lan_try_move`: 1,070.337 ms cumulative across 14 calls
- `player_command.end_turn`: 1,028.226 ms cumulative across 8 calls
- queue waits over 1000ms: none
- queue waits over 5000ms: none
- `static_plus_dynamic builds`: 0

Decision:
- Gate 3 remains open because Long Rest and perceived UI lag remain.
- G3-03 reduced one major static rebuild problem and should be preserved as a partial improvement.

## Additional Bugs Found During Smoke

### BUG-20260527-01 — Long Rest latency P0

Long Rest takes over a minute in browser smoke and traces at ~31s server-side.

Likely gates:
- Gate 3 latency
- Gate 4 Long Rest mechanics surface

Priority:
- P0

### BUG-20260527-02 — Free spells cannot be removed

Free spells can be added in Manage Spells but cannot be selected for removal like prepared spells.

Likely gate:
- Gate 2 targeted UI/capability follow-up

Priority:
- P2

### BUG-20260527-03 — Character switch can temporarily empty spell list

Switching characters can render the spell list empty until refresh.

Likely gate:
- Gate 2 targeted UI state follow-up

Priority:
- P2

### BUG-20260527-04 — Wild Shape movement reset

Wild Shape resets current movement to the new form's full speed.

Expected:
- Remaining movement = max(new form speed - distance already moved this turn, 0)

Likely gate:
- Gate 4 mechanics follow-up

Priority:
- P1

### BUG-20260527-05 — Combat targeting overlay blocks movement after Flurry/Fury kill

As Old Man, using Flurry/Fury can kill the target and leave the player unable to move because the melee targeting overlay blocks character movement.

Desired:
- Player should be able to move while retaining targeting mode, or the targeting mode should not trap the player after target death.

Likely gate:
- Gate 4 combat feature UX
- Gate 3 action-flow responsiveness

Priority:
- P1

### BUG-20260527-06 — Conditions/effects not supported correctly in DM console

Enemy effects can render as `condition [object]`.
Prone did not apply expected movement consequences.
There is no obvious stand-up action.
Enemy still received full movement despite being prone.

Expected:
- Condition labels render human-readable names.
- Prone can be stood up from.
- Standing from prone consumes half movement.
- Movement budget updates accordingly.

Likely gate:
- Gate 4 mechanics correctness
- DM control follow-up

Priority:
- P1

### BUG-20260527-07 — Lightning Bolt inconsistent save damage

Eldramar cast Lightning Bolt into two identical enemies.
Both passed the save.
One took half damage and one took no damage.

Expected:
- Lightning Bolt is half damage on successful save.
- Identical enemies with the same pass outcome should receive consistent pass damage unless a visible resistance/immunity/evasion rule applies.

Likely gate:
- Gate 2 spell contract correctness
- Gate 3 combat action correctness

Priority:
- P1

### BUG-20260527-08 — Resource pool UI updates slowly

Resource pool usage eventually applies, but the available count updates slowly.
This can make players think the action failed.
Page reload usually fixes it, but that is not acceptable as the stable workflow.

Likely gate:
- Gate 4 resource mechanics
- Gate 3 UI update responsiveness

Priority:
- P1

## Current Gate Decision

Gate 3 remains OPEN.

Preserve:
- G3-03 patch because it appears to eliminate the spell/wild-shape `static_plus_dynamic` rebuild path.

Do next:
- Root-cause and fix Long Rest latency.
- Keep unrelated bugs in backlog; do not bundle them into the Long Rest latency fix.


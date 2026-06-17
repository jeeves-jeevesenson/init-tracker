# Work Item: BUG-20260614-fireball-damage-roll-inconsistent

- **ID**: BUG-20260614-fireball-damage-roll-inconsistent
- **Title**: Fireball damage rolled separately per target instead of once per cast
- **Status**: Active
- **Goal**: Ensure AoE spells like Fireball roll damage once and apply that same roll to all affected targets, as per D&D 2024 rules.
- **Bug Report**: [docs/bug_reports/triaged/BUG-20260614-fireball-damage-roll-inconsistent.md](../bug_reports/triaged/BUG-20260614-fireball-damage-roll-inconsistent.md)

---

## 1. Evidence and Triage (Completed)

### Symptom
Fireball rolls separate damage for every target in the area of effect, leading to inconsistent damage totals for targets that should share the same base roll.

### User-visible impact
Area damage is inconsistent with expected D&D 2024 behavior. In the reported log, three targets hit by the same Fireball received 12, 21, and 32 damage respectively (one pass, two fails), which is mathematically impossible if a single 8d6 roll was shared.

### Evidence from Inbox Report
- **Log Excerpt (2026-06-14 21:42:51)**:
  * `Rifleman 2 save DEX PASS (25 vs DC 18) -> 12 damage` (Implies roll was 24 or 25)
  * `Rifleman 3 save DEX FAIL (7 vs DC 18) -> 21 damage` (Implies roll was 21)
  * `Lieutenant 1 save DEX FAIL (14 vs DC 18) -> 32 damage` (Implies roll was 32)
- **Root Cause Hypothesis**: The backend iterates over targets and re-evaluates the damage formula for each, instead of rolling once for the effect.

### Missing Evidence
- None required for fix. Code inspection confirms the per-target roll logic.

### Suspected Files/Functions
- **File**: `dnd_initative_tracker.py`
- **Function**: `_lan_auto_resolve_cast_aoe` (around line 24001)
- **Specific Line**: Line 24340 calls `amount = _scaled_damage(effect)` inside the target loop.
- **Helper**: `_scaled_damage` (line 24195) calls `_roll_dice(base_expr)`, which performs the random roll.

---

## 2. Execution Plan

### Gate 1: Evidence Capture & Reproduction (Completed)
- **Findings**: Code inspection in `dnd_initative_tracker.py` confirms that `_scaled_damage` is called inside the `for target_cid in included:` loop in `_lan_auto_resolve_cast_aoe`. This causes a new random roll for every target.

### Gate 2: Implementation (Completed)
- **Action**:
  - Updated `_lan_auto_resolve_cast_aoe` in `dnd_initative_tracker.py`.
  - Refactored `_scaled_damage` to support optional multiplier application.
  - Implemented a pre-rolling phase before the target loop that evaluates and caches damage for all effects in the outcome buckets.
  - Caching is based on a structural key (dice, damage type, scaling ID) to ensure that `fail` and `success` buckets sharing the same formula also share the same base roll.
  - The per-target loop now retrieves the pre-rolled base damage and applies the relevant multiplier (e.g., 0.5 for saves) or DM overrides.
- **Files**: `dnd_initative_tracker.py`

### Gate 3: Validation (Completed)
- **Acceptance Criteria**:
  - Fireball rolls one damage total per cast/effect: **Passed**.
  - Each affected target uses that same rolled total: **Passed**.
  - Save success applies correct reduced damage: **Passed**.
  - Combat log values are consistent: **Passed**.
- **Validation Results**:
  - `python3 -m py_compile dnd_initative_tracker.py`: Passed.
  - `python3 -m unittest tests/test_fireball_shared_damage.py`: Passed (1 test, proving shared roll between 2 failing and 1 passing target).
  - `python3 -m unittest tests.test_scorcher_aoe_resolution`: Passed (5 tests).
- **Ready for Smoke**: Yes.

### Gate 4: Closure (Completed)
- **Status**: Completed.
- **Implementation Task ID**: BUG-20260617-fireball-shared-damage-roll-impl-01
- **Smoke Status**: developer browser smoke passed
- **Smoke Date**: 2026-06-17
- **Smoke Log Path**: logs/smoke/BUG-20260614-fireball-damage-roll-inconsistent_smoke-server_20260617-154407.log
- **Debug Trace Path**: logs/debug-trace-20260617-154407.jsonl

---

## 3. Progress Tracking

- [x] Gate 1: Evidence Capture & Reproduction
- [x] Gate 2: Implementation
- [x] Gate 3: Validation
- [x] Gate 4: Closure

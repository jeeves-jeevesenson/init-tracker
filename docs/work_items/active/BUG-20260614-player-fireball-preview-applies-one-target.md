# Work Item: BUG-20260614-player-fireball-preview-applies-one-target

- **ID**: BUG-20260614-player-fireball-preview-applies-one-target
- **Title**: Player Fireball AoE preview includes multiple targets but resolution applies to only one
- **Status**: Active
- **Goal**: Identify and resolve the discrepancy between the frontend AoE targeting preview and backend spell resolution.
- **Bug Report**: [docs/bug_reports/triaged/BUG-20260614-player-fireball-preview-applies-one-target.md](../bug_reports/triaged/BUG-20260614-player-fireball-preview-applies-one-target.md)

---

## 1. Evidence and Triage

### Symptom
A player used Fireball, the frontend overlay showed two targets would be hit, but the cast resolution only affected one.

### Suspected Root Cause
Discrepancy between frontend geometry calculation (Pass 2/3) and backend resolution logic (Pass 6.8). Specifically, `_handle_cast_aoe_request` or the geometric primitive delegation in `spell_engine_primitives.py` may be using different inclusion rules than the frontend visualization.

### Evidence
- **Source**: Jun 13 live player smoke test.
- **Severity**: P1 Combat Correctness.

---

## 2. Execution Plan

### Gate 1: Evidence Capture & Reproduction (Active)
- **Goal**: Confirm the mismatch between `AoeSpec` visualization and backend unit inclusion.
- **Files**: `dnd_initative_tracker.py`, `spell_engine_primitives.py`.
- **Action**: Add instrumentation to `_handle_cast_aoe_request` to log the `AoeSpec` and the resulting `target_cids`. Use a reproduction script or unit test to simulate the specific Fireball placement.

### Gate 2: Implementation
- **Goal**: Align the inclusion logic.
- **Action**: Fix any discrepancies in `spell_engine_primitives.py` or the backend unit filtering.

### Gate 3: Validation
- **Goal**: Verify the fix with targeted unit tests and browser smoke check.
- **Action**: Run `tests/test_spell_aoe_targeting_primitives.py` and a new regression test covering the specific reported scenario.

---

## 3. Progress Tracking

- [ ] Gate 1: Evidence Capture & Reproduction
- [ ] Gate 2: Implementation
- [ ] Gate 3: Validation

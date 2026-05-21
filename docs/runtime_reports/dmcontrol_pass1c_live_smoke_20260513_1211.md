# Pass 1C Live Smoke Test Report

- **Date:** 2026-05-13
- **Tested Commit:** 6c771f6 (Fix DM control Black and Tan combat correctness)
- **Status Before:**
  ```
   M assets/web/dmcontrol/index.html
   M dnd_initative_tracker.py
   M docs/dm_control_surface_living_agent_plan.md
   M majorTODO.md
   M tests/test_dm_control_apply_results.py
  ?? docs/runtime_reports/
  ```

## Pre-flight Checks
- `git diff --check`: **FAILED** (trailing whitespace in index.html, dnd_initative_tracker.py, and tests)
- `py_compile dnd_initative_tracker.py`: **PASSED**
- JS syntax check `assets/web/dmcontrol/index.html`: **PASSED**

## Runtime Observation
- **Start Command:** `INIT_TRACKER_HEADLESS=1 ./.venv/bin/python3 serve_headless.py`
- **Readiness Line:** `DM operator surface: http://192.168.1.235:8787/dm` (~12:06:17)
- **Window:** 12:06:17 - 12:11:17 (5 minutes)
- **App Stability:** Stayed running for the full 5 minutes.
- **Shutdown:** Clean (SIGTERM).

### Server Logs & Events
- `[2026-05-13 12:06:07] WARNING Spell YAML level-0-5-tag-review.yaml missing name; skipping preset.`
- `[2026-05-13 12:06:12] WARNING Player YAML Fred: inventory item 'dagger' is missing explicit instance_id; using fallback 'derived:dagger__001'.`
- `[2026-05-13 12:06:58] INFO LAN session connected ...`
- `[2026-05-13 12:08:38] INFO LAN session ... claimed Dorian`
- `[DEBUG] dm_resolve_monster_capability_targets took 12.3789s` (and similar entries ~11-12s)

### Technical Observations
- The `dm_resolve_monster_capability_targets` debug log appeared frequently, consistently taking between 11.4s and 12.4s. This suggests a potential bottleneck in target resolution that may warrant investigation if it impacts UX responsiveness.
- No Python exceptions or tracebacks were observed.
- LAN connections and character claims were successful.

## Recommended Next Pass
- **Pass 1D:** Investigate the target resolution latency and continue with planned UI/UX refinements for the DM control surface.

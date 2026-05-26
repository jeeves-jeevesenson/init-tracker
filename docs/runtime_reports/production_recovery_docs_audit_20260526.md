# Production Recovery Audit — 2026-05-26 (Hardened)

## 1. Hardening Pass Summary (Gate 0B)
This pass deepened the initial audit by mapping every product surface to specific source files, unit tests, and known runtime contradictions.

## 2. Hardened Contradiction Matrix

| ID | Contradiction | Evidence | Impact |
| :--- | :--- | :--- | :--- |
| **C-001** | **Broken Test Helper** | `tests/test_dm_tactical_map_routes.py` L2988 calls `lan._dm_console_snapshot()`. Source L4040 shows it is a local closure in `InitiativeTracker.start_fastapi`. | Integration tests are currently a false negative or failing with AttributeError. |
| **C-002** | **WebSocket Misconception** | `hotfix_dm_map_combat_lite_regression_20260523.md` claims `/dmcontrol` uses polling. `assets/web/dmcontrol/index.html` confirmed to use `setInterval(fetchState, 2000)`. | Docs and Backend support `workspace=dmcontrol` for WebSockets, but the primary surface does not use it. |
| **C-004** | **Map Regression** | Playability pass (2026-05-22) disabled tactical snapshots too broadly. Hotfix (2026-05-23) restored them but DM still reports issues. | DM Map Workspace is likely still missing critical state or sync. |
| **C-006** | **Experimental Leakage** | `scripts/trace_latency_summary.py` showed `_dm_tactical_snapshot` as a top cumulative span (234s) before the "amputation" pass. | If flags aren't strictly checked in `_lan_force_state_broadcast`, lag persists. |

## 3. Missed in First Pass
- **WebSocket Polling Divergence**: The first pass assumed `/dmcontrol` might use WebSockets because the backend supports the workspace. Deep audit confirmed it polls.
- **Trace Evidence**: The first pass didn't include the specific 11s wild-shape lookup delay or the 33s long-rest HTTP hang.
- **Merge Semantics**: Missed ADR-0002 and ADR-0003 which are critical for "brittle" spell/capability areas.

## 4. Unresolved Unknowns
- Why `dmcontrol` has WebSocket backend support if the frontend only polls.
- Whether the 11s wild-shape delay is a cache-miss or a complex DB lookup.
- If the `lan._dm_console_snapshot()` test calls were once valid (legacy) or are pure hallucinations.

## 5. Recommended Next Task
**Gate 1: Map Surface Contract Restoration**
- Fix the `AttributeError` in `tests/test_dm_tactical_map_routes.py`.
- Verify the `?workspace=dmcontrol` polling returns full tactical state.
- Restore DM map interaction.

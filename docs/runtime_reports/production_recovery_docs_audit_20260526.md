# Production Recovery Audit — 2026-05-26 (Operational)

## 1. Operational Hardening Summary (Gate 0C)
This pass transformed the recovery plan from a high-level summary into a detailed operational guide. We established a strict "Definition of Production-Ready," expanded all matrices to include the full product surface, and fully detailed Gates 1 through 6.

## 2. Key Operational Enhancements
- **Evidence-Backed Status Labels**: Replaced vague "Verified" labels with strict definitions (e.g., "Verified by unit tests only," "Known P0 history / needs revalidation").
- **Exhaustive Product Surface Matrix**: 20-row matrix covering every required area from core combat to experimental quarantine.
- **Detailed Map Contract**: Defined intended behavior and verification paths for all 10 critical map-related API and UI endpoints.
- **Full Gate Specification**: Gates 1 through 6 now include explicit "Allowed Files," "Forbidden Scope," and detailed "Pass/Fail/Rollback" criteria.
- **Quarantine Logic**: Documented the exact flag-based mechanisms (`INIT_TRACKER_ENABLE_SHIP_SURFACES`) for isolating experimental features.

## 3. Updated Contradiction Matrix (Gate 0C Addendum)

| ID | Status | Resolution Path |
| :--- | :--- | :--- |
| **C-001** | Open | Gate 1: Fix `tests/test_dm_tactical_map_routes.py`. |
| **C-002** | Confirmed | Documented as "Polling" for frontend; "WS-capable" for backend. |
| **C-003** | To be Removed | Gate 5: Delete legacy `/api/dm/monster-pilot` routes. |
| **C-004** | Blocked | Gate 1: Restoration of tactical snapshot hydration. |
| **C-005** | brittle | Gate 2: Implementation of ADR-0002 non-clobber merge logic. |
| **C-006** | Open | Gate 5: Hardening of flag checks in broadcast loops. |
| **C-007** | Open | Gate 6: Verification of startup timing and public IP reachability. |

## 4. Remaining Unknowns
- **Wild-Shape Latency**: The exact cause of the 11s delay in `test_wild_shape.py` is still being investigated as part of Gate 3 research.
- **Experimental Code Coverage**: The status of "Boarding" and "Structure Objects" remains "Unknown" until Gate 5 research begins.

## 5. Recommended Next Task
**Gate 1: Map Surface Contract Restoration**
- Surgical fix for `tests/test_dm_tactical_map_routes.py`.
- Validation of `/dmcontrol` polling with `?workspace=dmcontrol`.
- Verification of DM map interaction restoration.

# WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture

Status: Completed

## Goal

Open and complete a bounded post-implementation smoke evidence checkpoint for commit 82b996a.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation.md`
- `docs/runtime_reports/dm_console_combat_service_read_model_composition_minimal_implementation_20260707.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_smoke_evidence_20260707.md`
- `logs/smoke/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture_smoke-server_20260708-122320.log`
- `logs/debug-trace-20260708-122320.jsonl`
- `scripts/snapshot_lan_hot_path_latency_harness.py`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260707-dm-console-combat-service-read-model-composition-smoke-evidence-capture.md`
- `docs/planning/living_docs/dm_console_combat_service_read_model_composition_smoke_evidence_capture_20260708.md`
- `docs/runtime_reports/dm_console_combat_service_read_model_composition_smoke_evidence_20260708.md`

## Evidence Capture

The smoke proves that headless startup, debug trace creation, `/dm` and `/` advertisement, LAN server hoisting on port 8787, browser LAN session connection/disconnection, and claim/unclaim/claim flows still work.

The harness parsed `219,108` valid JSON objects and `0` malformed/non-object lines under a `112`-combatant / `102`-monster shape.

- `combat_service.combat_snapshot` p95 improved: `500.641 ms` -> `384.238 ms` (~23% reduction).
- `dm.console.combat_snapshot.service_call` p95 improved: `501.904 ms` -> `386.362 ms` (~23% reduction).
- `http.request:/api/dm/combat` p95: `936.898 ms` -> `1352.821 ms`.

Keep commit `82b996a`. Recommended next work item is `WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint` as a planning / evidence checkpoint to address the route/request-level overhead.

## Validation

All required validation commands were executed successfully:
- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-122320.jsonl`
- `timeout 10s git diff --check`
- `git status --short`

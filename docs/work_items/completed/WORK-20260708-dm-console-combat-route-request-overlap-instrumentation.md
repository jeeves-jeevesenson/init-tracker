# WORK-20260708-dm-console-combat-route-request-overlap-instrumentation

Status: Completed

## Goal

Add minimal trace-only instrumentation to distinguish route/request overhead for `/api/dm/combat` after the service read-model composition refinement was accepted.

## Files Inspected

- `dnd_initative_tracker.py`
- `server_runtime.py`
- `tests/test_server_runtime.py`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `docs/work_items/current_work.md`

## Files Changed

- `dnd_initative_tracker.py` (added threadpool queue timing trace, response build trace, and dynamic debug trace counts logging)
- `tests/test_server_runtime.py` (updated mock server runtime client and added assertions in `test_combat_route_instrumentation_under_debug_trace`)
- `scripts/snapshot_lan_hot_path_latency_harness.py` (supported compiling aggregated counts and formatting threadpool queue and response build spans)
- `docs/work_items/current_work.md` (updated status ledger to complete)

## Analysis and Decisions

1. **Threadpool Queue Scheduling Instrumentation**: Wrapped threadpool offloading of the snapshot read in a `dm.console.threadpool_dispatch_queue` span. Captured the context context (`dm_console_route` or `dm_console_route_tactical`) so that it can be attributed clearly in the latency harness, and preserved low cardinality by stripping names/IDs.
2. **Response Serialization Instrumentation**: Wrapped the FastAPI payload copy and dictionary construction in a `dm.console.route_response_build` span.
3. **Dynamic Client/Combatant Count Logging**: Embedded live combatant, player, monster, and websocket connection counts directly into the threadpool dispatch span properties dynamically querying `lan_controller` without mutating `snap_req.params` or polluting the facade request structure.
4. **Harness Support**: Extended the standard-library latency harness to read and aggregate the new spans (`dm.console.threadpool_dispatch_queue` and `dm.console.route_response_build`) and display live counts.

## Validation

All required validation commands ran successfully:
- `timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py` (86 tests passed successfully)
- `python3 -m py_compile dnd_initative_tracker.py tests/test_server_runtime.py scripts/snapshot_lan_hot_path_latency_harness.py` (compiled successfully)
- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260708-122320.jsonl` (harness executed cleanly)
- `timeout 10s git diff --check` (passed with zero formatting or trailing whitespace issues)

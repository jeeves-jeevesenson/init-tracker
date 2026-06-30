# WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation

Status: Completed

## Goal

Implement the minimal DM-console read-model cache refinement selected by `WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision`.

The implementation keeps cache ownership in the legacy DM-console helper/prebuild path, adds tactical-mode metadata to the existing cached DM snapshot state, and requires `include_tactical` match before cache reuse.

## Files Changed

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation.md`

## Implementation Summary

Added legacy-owned cached DM snapshot mode metadata:

- `_cached_dm_snapshot_include_tactical`

`LanController.__init__()` now initializes:

- `_cached_dm_snapshot`
- `_cached_dm_snapshot_at`
- `_cached_dm_snapshot_include_tactical`

`LanController._dm_console_snapshot()` now:

- Resolves `include_tactical` to a boolean flag.
- Reuses `_cached_dm_snapshot` only when the cached snapshot is still within the existing `0.25` second TTL and `_cached_dm_snapshot_include_tactical` is a boolean matching the requested `include_tactical` mode.
- Clears `_cached_dm_snapshot`, `_cached_dm_snapshot_at`, and `_cached_dm_snapshot_include_tactical` with the existing one-shot cache clear.
- Rebuilds instead of reusing when cached tactical metadata is missing, expired, or mismatched.

The existing prebuild path in `_lan_force_state_broadcast()` now records `_cached_dm_snapshot_include_tactical = bool(include_tact)` alongside `_cached_dm_snapshot` and `_cached_dm_snapshot_at`.

## Preserved Behavior

- Cache ownership remains in `LanController` / the legacy DM-console prebuild path.
- `ServerRuntimeFacade.read_snapshot()` remains unchanged and owns no cache state.
- `GET /api/dm/combat` remains unchanged and still passes explicit `include_tactical` context.
- TTL remains `0.25` seconds.
- Payload shapes and route responses are unchanged.
- No route migration, route-side offload, static hydration, invalidation framework, LAN dynamic snapshot reuse, response schema change, gameplay/combat behavior change, queue behavior change, LAN/Tk/WebSocket behavior change, deployment, commit, or push was performed.

## Tests Added

Focused regression coverage in `tests/test_server_runtime.py`:

- Cached DM-console payload is reused when `include_tactical` metadata matches.
- A tactical cached payload is not reused for a non-tactical request.
- A non-tactical cached payload is not reused for a tactical request.

Existing facade tests continue to prove `read_snapshot(dm_console)` delegates with explicit `include_tactical` and does not introduce facade-owned cache behavior.

## Validation

Required validation run:

- `.venv/bin/python -m pytest tests/test_server_runtime.py -q`
- `timeout 10s git diff --check`
- `git status --short`

`tests/test_server_runtime.py` result:

- `68 passed, 29 subtests passed in 2.48s`

## Next Safe Action

Run bounded developer smoke/evidence for `GET /api/dm/combat` and `GET /api/dm/combat?workspace`, or commit the completed implementation if requested.

Do not proceed to facade-owned cache, TTL increase, route-side read offload, LAN dynamic snapshot reuse, static hydration, another read-route adoption, player-command routes, combat mutation routes, rules-aware move, AoE create, structures, ships, boarding links, or high-risk direct gameplay route migration without a new active work item.

## Developer smoke follow-up — 2026-06-30

Smoke status: passed.

Evidence:
- Developer reported: "dm worked fine."
- Smoke log: `logs/smoke/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation_smoke-server_20260630-183429.log`.
- Debug trace: `logs/debug-trace-20260630-183429.jsonl`.
- Headless server started and advertised DM/player surfaces.
- LAN session connected and claimed `Dorian`.
- `GET /api/dm/combat?workspace` returned HTTP 200.
- Observed route trace near the smoke interaction: HTTP request about 29 ms, `_dm_console_snapshot` about 21.7 ms, `_dm_tactical_snapshot` about 3.6 ms, and `_lan_snapshot` about 3.4 ms.
- No stale tactical/non-tactical cross-mode data or responsiveness problem was reported by the developer.

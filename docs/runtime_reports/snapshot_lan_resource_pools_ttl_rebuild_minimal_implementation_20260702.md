# Snapshot/LAN Resource-Pools ttl_rebuild Minimal Implementation Runtime Report - 2026-07-02

## Scope

This report records local implementation and focused validation for a narrow `resource_pool_mode=ttl_rebuild` refinement.

No server was started. No browser smoke was run. No logs were edited. No deploy, restart, SSH, push, commit, production topology change, route movement, payload/schema change, TTL change, static hydration change, startup static-fields change, WebSocket change, queue change, or gameplay/resource semantic change was performed.

## Implementation Summary

The tracker now keeps a base-normalized resource-pools cache separate from the dedicated resource-pools payload cache.

The base cache reduces repeated work during authoritative TTL rebuilds by reusing normalized pool lists when:

- the player name is unchanged;
- the cached player profile object is unchanged;
- item, magic-item, and consumable registry signatures are unchanged.

Every rebuild still creates a fresh `resource_pools` payload and still runs temporary condition augmentation. The base cache is cleared or bypassed for force rebuilds, `"resource_pools"` invalidation, full player-YAML refresh, and player-YAML write/update seams.

The existing one-second throttle and fallback/backfill behavior from commit `95bbdf6` remain unchanged.

## Focused Test Coverage

Added coverage in `tests/test_server_runtime.py` for:

- base normalized resource-pool reuse for unchanged player profiles;
- fresh temporary pool augmentation on each rebuild without accumulation in the base cache;
- registry signature changes forcing base normalization to rerun;
- low-cardinality `ttl_rebuild_base_cache_all_hit` result labeling.

Existing resource-pools cache tests continue to cover dedicated cache hit, LAN snapshot backfill, force rebuild on static/invalidation, and rebuild failure fallback.

## Validation

Commands used for this pass:

```bash
.venv/bin/python -m py_compile dnd_initative_tracker.py
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Python compile passed. The focused pytest command passed after an obvious local helper-name collision was fixed, with final result `80 passed in 1.08s`. Final diff/status command output is recorded in the final agent report.

## Runtime Evidence Gap

This implementation did not generate a new debug trace and did not run the latency harness against live traffic because server start and browser smoke were explicitly out of scope.

Recommended next evidence step:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py <new-debug-trace.jsonl>
```

Use a developer-run targeted smoke to compare `lan.snapshot.resource_pools` slow-threshold counts and `resource_pool_mode=ttl_rebuild_*` submodes before selecting any further optimization.

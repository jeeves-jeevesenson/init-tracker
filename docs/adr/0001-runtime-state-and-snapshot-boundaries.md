# ADR 0001: Runtime State and Snapshot Boundaries

Status: Proposed
Date: 2026-05-22

## Context

During recent developmental iterations (specifically around Pass 8B and 8C), the application encountered critical regressions where core UI elements like Spells, Manage Spells, and Resource Pools rendered as completely empty for casters and resource-using players on fresh page load or reconnection.

These regressions stemmed from a fundamental architectural boundary confusion:
1. The backend cached snapshot (`_cached_snapshot`) was treated as the ultimate source of truth for certain capability and static fields (such as `player_spells`, `player_profiles`, and `resource_pools`).
2. When the backend performed "cheap" state-only ticks or delta snapshots (e.g., when idle or when no clients were connected), it omitted large, static-rich capability data.
3. This "stripped" or poisoned snapshot was then stored in `_cached_snapshot`, permanently erasing the capability data from the read cache.
4. Newly connecting clients requesting static data or full updates received the empty fields from the poisoned cache.

## Decision

We establish a strict, non-negotiable boundary between **Authoritative Runtime State** and **Transport/Read Projections**:

1. **Authoritative Runtime State Is the Absolute Source of Truth:**
   - Active combat, combatant data, player selections, and profiles are held in native runtime objects (e.g., `InitiativeTracker.combatants`, `player_profiles`, spells databases).
   - The transport layer cache (`_cached_snapshot`), websocket message payloads, JSON serialization outputs (`_json_safe`), and frontend Javascript local variables are **projections** only.

2. **Projections Must Be Fully Rebuildable:**
   - Projections are ephemeral read-models.
   - It must be possible to completely discard the `_cached_snapshot` and rebuild it at any point from the backend's authoritative runtime models without data loss.

3. **Caches and Projections Must Not Hold Authoritative State:**
   - No data domain (including `player_spells`, `resource_pools`, `player_profiles`, `inventory`, `equipment`, or `combatants`) may exist solely in `_cached_snapshot` or frontend state.
   - Any read optimization (such as delta snapshots or skipping static fields during idle ticks) must never overwrite or poison the capability layers of the cache. A merge or carryover protocol must enforce this separation.

## Consequences

### Positive
- **Guaranteed Recovery:** Reconnecting or newly joining players will always be served full, hydrated capability data.
- **Robust Optimizations:** The backend can safely perform high-frequency cheap delta broadcasts without risking corruption or erasure of the underlying player capabilities.
- **Testability:** Caches and serialization can be unit-tested as pure projections separate from gameplay rules.

### Negative
- **Minor Overhead:** Building full projections occasionally requires merging or rebuilding data structures on client connection or major state invalidation.

### Operational
- The server must maintain the true capability models (`player_spells`, `player_profiles`, `resource_pools`, `inventory`, `equipment`) outside of the cache.
- Any tick or event that mutates player capability data must explicitly invalidate the cached static/full projections, triggering a fresh build rather than modifying cache fields in-place.

## Contract / Tests Required

- `test_lan_first_load_spell_catalog_non_empty`: Verifies that first-load static data is fully populated with the spell catalog.
- `test_lan_first_load_player_spells_for_seeded_caster`: Verifies that first-load static data has seeded spells for players.
- `test_lan_controller_carryover_prevents_static_erasure`: Verifies that updating the cache with a stripped snapshot does not erase static/capability data from the cache.

## Migration Notes
- Implement `LanController._merge_cached_snapshot_carryover` to ensure cheap, static-less snapshots do not overwrite rich static fields in the cached projection.
- Modify `LanController._static_data_payload` to backfill missing state from the authoritative backend objects if the cache contains empty or incomplete structures.

# ADR 0004: Cache Invalidation Domains

Status: Proposed
Date: 2026-05-22

## Context

To minimize CPU overhead and serialization time during high-frequency combat ticks, the application implements read caches for LAN snapshots (`_cached_snapshot` and `_cached_static_payload`).

However, cache invalidation has historically been ad-hoc or coarse-grained. A change in one domain (e.g., adding a prepared spell or equipping a sword) would fail to invalidate the transport caches, leaving the client with stale capabilities. Conversely, coarse invalidation (wiping everything on every tick) ruined the performance gains.

We need a systematic, reliable, domain-specific cache invalidation model.

## Decision

We establish a **Domain-Based Cache Invalidation** architecture:

1. **Caches Are Ephemeral Projections:**
   In line with ADR 0001, caches (`_cached_snapshot`, `_cached_static_payload`, and `_monster_choices_cache`) are read-only transport models and must be completely rebuildable.

2. **Domain-Specific Invalidation Paths:**
   Every mutating command on the backend must explicitly declare which data domains it invalidates. The cache invalidation framework will then wipe *only* the relevant cached projections, forcing them to rebuild on the next request or broadcast.

   The invalidation mapping is defined as:

   | Mutating Event / Command | Invalidated Domains | Cache Cleanup Action |
   |---|---|---|
   | **Spell Management** (Add, prepare, remove spells) | `player_spells`, `spell_capabilities` | Wipes `_cached_static_payload`, triggers `include_static=True` for next broadcast. |
   | **Resource Pool Mutation** (Spend, restore, override pools) | `resource_pools`, `dynamic_state` | Wipes pool cache, forces broadcast. |
   | **Inventory & Equipment** (Add item, equip weapon) | `inventory_equipment`, `attack_options` | Wipes `_cached_static_payload`, recalculates action panels. |
   | **Combat Turn / Movement** (End turn, move token) | `combat_state`, `map_state` | Wipes delta snapshots only, sends `lan_state_delta`. |
   | **Long Rest / Rest Commands** | All domains | Wipes full caches, forces broad refresh across all clients. |
   | **Monster Addition / Library Refreshes** | `monster_choices`, `combatant_roster` | Wipes `_monster_choices_cache` and static projections. |

3. **Optimization Safety Constraint:**
   No performance optimization (such as caching static components or skipping snapshots when idle) is acceptable if it violates the correctness of first-load capability retrieval or partial-update non-clobber rules. Correctness and state safety are strictly prioritized over raw performance.

## Consequences

### Positive
- **No Stale Data:** Changes to player inventories, spells, and resource definitions propagate immediately to the UI because the static payload cache is invalidated correctly.
- **Controlled CPU Overhead:** High-frequency movement ticks do not trigger expensive spell-catalog or profile rebuilds, keeping gameplay responsive.
- **Safety Invariant:** Establishes a predictable pattern for adding new features.

### Negative
- **Explicit Invalidation Calls:** Developers must remember to invoke the appropriate cache invalidation helper when implementing new commands in `player_command_service.py` or `combat_service.py`.

### Operational
- Add dedicated helper methods in `LanController`:
  - `_invalidate_lan_static_snapshot_cache(reason)`: Clears `_cached_static_payload` and schedules a rich broadcast.
  - `_invalidate_lan_dynamic_snapshot_cache()`: Clears the dynamic components.
- Ensure that rest commands (long/short rest) and equipment mutations trigger complete static invalidations.

## Contract / Tests Required

- `test_static_invalidation_causes_static_component_rebuild`: Asserts that dirtying the static cache successfully triggers a full rebuild of presets and profiles.
- `test_long_rest_resource_values_reflect_backend_after_payload`: Verifies that a long rest invalidates caches and sends updated pool values.

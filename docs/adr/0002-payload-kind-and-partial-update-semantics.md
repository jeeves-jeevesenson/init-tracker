# ADR 0002: Payload Kind and Partial Update Semantics

Status: Proposed
Date: 2026-05-22

## Context

In modern client-server architectures with high action frequency, optimization is usually achieved by sending "partial" state updates (deltas) instead of complete static and dynamic state payloads.

However, without explicit semantics defining what missing keys, empty objects (`{}`), empty arrays (`[]`), and `null` values mean, the client's merge logic becomes fragile.
- In `assets/web/lan/index.html`, we witnessed a bug where partial state updates containing empty structures (e.g., `{}`) was blindly assigned to frontend state keys, wiping out populated arrays and objects like `player_spells`, `player_profiles`, and `resource_pools`.
- Newly connected clients or recovering reconnects would occasionally receive empty objects, resulting in empty panels on their UI.

## Decision

To avoid clobbering capability and static data during high-frequency delta broadcasts, we define explicit **Payload Kinds** and **Merge Semantics**:

1. **Explicit Payload Kinds:**
   Every payload sent over the websocket or API must define its kind:
   - `lan_static_full`: A complete payload of static and capability definitions (sent on initial connection or major data refresh).
   - `lan_state_full`: A complete snapshot of dynamic state (HP, resource values, positions, active turns).
   - `lan_state_delta`: A partial update of high-frequency dynamic changes.
   - `dm_state_full`: Authoritative full state for the DM console.
   - `dm_state_delta`: Delta state update for the DM console.
   - `dm_map_state_full`: Map layout, tokens, terrain, and active AoE zones.
   - `intentional_clear`: An explicit, intentional command payload indicating that a specific data field must be wiped or reset.

2. **Partial Update Non-Clobber Rules (The Merge Contract):**
   When merging payloads on the frontend, the following mapping rules apply:

   | Key State in Incoming Payload | Full Payload Semantics | Partial / Delta Payload Semantics |
   |---|---|---|
   | **Key is Missing** | Preserve current client value. | Preserve current client value (no-op). |
   | **Key is Present with Value** | Overwrite with new value. | Overwrite with new value. |
   | **`{}` or `[]` (Empty)** | Authoritative empty (only if allowed by that domain). | **DO NOT CLEAR** static/capability data. Treat as "no update" or partial ignore. |
   | **`null`** | Invalid by default unless explicit field contract defines nullability. | Invalid by default unless explicit field contract defines nullability. |
   | **`intentional_clear` Action** | Reset/wipe the target domain state. | Reset/wipe the target domain state. |

## Consequences

### Positive
- **Deterministic Frontend Behavior:** The frontend will never accidentally erase its locally stored spellbooks, catalogs, resource selectors, or inventory when a delta packet containing `{}` or missing keys arrives.
- **Payload Size Reduction:** Deltas can remain ultra-slim, omitting all static keys without risking client UI clobbering.
- **Clear Contracts:** Prevents ad-hoc fixes in frontend event loops.

### Negative
- **Increased Merge Logic Complexity:** The frontend client must implement and consistently use merge helpers (such as `isEmptyPlainObject`) across all websocket action handlers.

### Operational
- The frontend static data handler (`msg.type === "static_data"`) must use `isEmptyPlainObject()` to prevent empty server objects from overriding populated state values during client connection or reconnection events.

## Contract / Tests Required

- `test_lan_state_delta_does_not_clear_spell_capabilities`: Asserts that a delta payload containing empty keys does not clear the caster's spells on the client.
- `test_resource_pools_survive_state_delta`: Asserts that a delta update does not erase the resource selectors.
- `test_manage_spells_empty_catalog_is_error_not_silent_empty`: Verifies that receiving an empty catalog throws a trace error instead of failing silently.

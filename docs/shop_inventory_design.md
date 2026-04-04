# Shop/Inventory Phase 0 Design Contract

This document freezes the player-owned item data model for the planned standalone web shop/inventory system.

## Canonical source of truth

After cutover, player-owned shop/inventory state must live in exactly two places:

- `inventory.currency`
- `inventory.items[]`

No other section may be treated as authoritative for owned, equipped, attuned, or per-item runtime state.

### Currency location

Currency is stored at `inventory.currency`, for example:

```yaml
inventory:
  currency:
    gp: 125
    sp: 4
    cp: 0
```

## Owned item model

Each entry in `inventory.items[]` is an owned item record.

Required model decisions:

- Every equippable item (weapon, armor, arcane focus, or other equippable) is non-stackable and stored as a unique owned instance.
- Every equippable unique owned instance must have a stable instance identifier.
- Stackable records are only for consumables and similar non-equippables.
- Equipped state is stored on the owned item record and must persist in player YAML.
- Attuned state is stored on the owned item record and is managed from inventory UI.
- Magic items declare whether they require attunement (`requires_attunement` on item definitions).

## Stackable vs unique

- **Stackable** (`stackable: true`): consumables and similar non-equippables; quantity is represented in one inventory row.
- **Unique** (`stackable: false`): all equippables and magic gear-like items; each instance is a separate row with its own instance id and state.

### Example: stackable consumable

```yaml
inventory:
  items:
    - instance_id: "consumable-healing-potion"
      source_id: "healing_potion"
      source_path: "Items/Consumables/healing_potion.yaml"
      stackable: true
      quantity: 3
      equipped: false
      attuned: false
      state: {}
```

## Equipment persistence

Owned item equipment state must be persisted directly on each owned item (`equipped: true|false`) so players do not need to re-equip after restart.
Weapon hand-slot selection is also owned-instance state on `inventory.items[]`:

- `equipped_slot: main_hand|off_hand`
- `selected_mode: one|two` for versatile/two-handed usage

This replaces transient/local-only hand selectors as the source of truth.

## Attunement rules

- Attunement is managed from inventory UI.
- Only owned items can be attuned.
- Items that do not require attunement must not be attuned.
- Items requiring attunement are active only when both equipped and attuned.
- Attunement cap is locked at **3** concurrently attuned items per character.

## Item-held pools/charges

Item-granted pools/charges/runtime counters must be stored on the owned item instance (`inventory.items[].state`), not as permanently rewritten
character-wide resources simply because an item is equipped.

Active grants are projected from item instances based on activation rules:

- for normal equippables: active when `equipped: true`
- for attunement-required items: active when `equipped: true` and `attuned: true`

### Example: unique magic item with equipped, attuned, and item-held state

```yaml
inventory:
  items:
    - instance_id: "mi-ring-of-storing-001"
      source_id: "ring_of_spell_storing"
      source_path: "Items/Magic_Items/ring_of_spell_storing.yaml"
      stackable: false
      quantity: 1
      equipped: true
      attuned: true
      state:
        charges:
          current: 3
          max: 5
        granted_pools:
          stored_spell_levels:
            current: 2
            max: 5
```

## Legacy removal

The legacy duplicate truths are retired and must not survive cutover:

- `inventory.equipped`
- `magic_items.equipped`
- `magic_items.attuned`
- `magic_items.items`
- any other duplicate equipment or attunement list that mirrors item-instance state

Backward-compatible dual-state behavior is explicitly rejected for this model.

## Out of scope for this doc

This Phase 0 contract does **not** define:

- routes or API handlers
- migration code
- frontend implementation details
- catalog loading implementation

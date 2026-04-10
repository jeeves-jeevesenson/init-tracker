# Items YAML Data

Item definitions are split by type to support structured automation:

- `Items/Weapons/` — weapon YAML files
- `Items/Armor/` — armor YAML files
- `Items/Magic_Items/` — magic items (including magic weapons/armor)
- `Items/Consumables/` — consumable item YAML files
- `Items/Gear/` — adventuring gear YAML files
- `Items/Shop/` — shop catalog overlay YAML files (sellability/category/price metadata)

## Preferred format (primary source of truth)

Use **one YAML file per item** where the filename is the item id (for example `longsword.yaml`).

- Mundane weapon files live in `Items/Weapons/`
- Armor files live in `Items/Armor/`
- Magic weapon/armor files live in `Items/Magic_Items/` and are still resolved for weapon/armor presets at runtime
- Consumable files live in `Items/Consumables/`
- Adventuring gear files live in `Items/Gear/`
- Each file should contain a single item object with an `id`

This per-item layout is what runtime item loading now expects first.

## Canonical item definition fields

All item files share these optional metadata fields. The runtime treats absent
fields as their documented default.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | string | — | **Required.** Stable snake_case identifier, unique within its bucket. |
| `name` | string | — | **Required.** Human-readable name. |
| `type` | string | same as bucket | Sub-type within the bucket (e.g. `longsword`, `plate`, `potion`). |
| `category` | string | — | Broader category grouping (e.g. `martial_melee`, `light`). |
| `description` | string | — | Descriptive text; may be multiline. |
| `rarity` | string | — | One of `common`, `uncommon`, `rare`, `very rare`, `legendary`, `artifact`. |
| `requires_attunement` | bool | `false` | Whether attunement is required to use this item. |
| `stackable` | bool | `false` | Whether multiple quantities can be consolidated into one inventory entry. |
| `grants` | dict | — | Mechanical automation (spells, actions, pools, modifiers, aura). |
| `source` | dict | — | Provenance tracking (`provider`, `edition`, `url`). |
| `import_notes` | list | — | Free-text notes added during import; editorial only. |

## Item behavior tiers

Items are classified into three tiers at runtime based on their definition:

| Tier | Criteria | Runtime behaviour |
|---|---|---|
| **A** | Has a `grants` dict with at least one of: `spells`, `actions`, `pools`, `modifiers`, `aura`. | Full mechanical automation. Attunement enforced if `requires_attunement: true`. |
| **B** | Has a non-empty `description` string, a `rarity` value, or `requires_attunement: true`. | Ownership, display, and shop purchase supported. No automation. |
| **C** | Just `id` and `name`; no description/rarity/grants. | Legal stub. Safe to own, buy, and display. No automation or description. |

The tier is computed at load time and exposed in shop API responses as `item_tier`.

## Legacy format (optional)

Catalog files with `weapons: []` or `armors: []` are still supported for backward compatibility,
but they are optional and no longer required.

## Non-item definition files

Some YAML files are metadata, not items. For example:

- `properties_*.yaml` files that define shared weapon properties

These files are intentionally ignored by the item registry unless they contain actual item records.

## Overlay bucket

`Items/Shop/` is an overlay layer for curated shop listings. Item behavior still belongs in the item-definition buckets (`Weapons`, `Armor`, `Magic_Items`, `Consumables`, `Gear`).

## Catalog generation

Use `scripts/build_shop_catalog.py` to generate or refresh `Items/Shop/catalog.yaml` from all
definition files. Existing entries are preserved. New entries are added as disabled (admin must
enable them). Run `--dry-run` to preview what would be added without writing.

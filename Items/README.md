# Items YAML Data

Item definitions are split by type to support structured automation:

- `Items/Weapons/` — weapon YAML files
- `Items/Armor/` — armor YAML files
- `Items/Magic_Items/` — magic items (including magic weapons/armor)
- `Items/Consumables/` — consumable item YAML files
- `Items/Shop/` — shop catalog overlay YAML files (sellability/category/price metadata)

## Preferred format (primary source of truth)

Use **one YAML file per item** where the filename is the item id (for example `longsword.yaml`).

- Mundane weapon files live in `Items/Weapons/`
- Armor files live in `Items/Armor/`
- Magic weapon/armor files live in `Items/Magic_Items/` and are still resolved for weapon/armor presets at runtime
- Consumable files live in `Items/Consumables/`
- Each file should contain a single item object with an `id`

This per-item layout is what runtime item loading now expects first.

## Legacy format (optional)

Catalog files with `weapons: []` or `armors: []` are still supported for backward compatibility,
but they are optional and no longer required.

## Non-item definition files

Some YAML files are metadata, not items. For example:

- `properties_*.yaml` files that define shared weapon properties

These files are intentionally ignored by the item registry unless they contain actual item records.

## Overlay bucket

`Items/Shop/` is an overlay layer for curated shop listings. Item behavior still belongs in the item-definition buckets (`Weapons`, `Armor`, `Magic_Items`, `Consumables`).

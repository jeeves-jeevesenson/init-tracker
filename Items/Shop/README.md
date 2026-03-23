# Shop Catalog Overlay

`Items/Shop/` stores **shop-facing overlay metadata** for item listings.

## Purpose

Shop files do **not** redefine item behavior. They only describe:

- whether an item is sold (`enabled`)
- how it is grouped in the shop UI (`shop_category`)
- what it costs (`price`)

## Source of truth split

- Item-definition YAMLs in `Items/Weapons/`, `Items/Armor/`, `Items/Magic_Items/`, and `Items/Consumables/` remain the source of truth for item rules/behavior.
- Shop catalog YAML in `Items/Shop/` is the source of truth for sellability/category/price metadata.

Later loader/API code should join shop catalog entries to item definitions by `item_id` + `item_bucket`.

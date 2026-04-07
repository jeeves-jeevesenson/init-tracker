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

## Admin API support (`/shop_admin` + backend)

The backend exposes unprotected admin-facing catalog write helpers used by the current `/shop_admin` LAN UI:

- `POST /api/shop/catalog/validate` validates a proposed catalog payload **in memory** and returns normalized entries for preview.
- `GET /api/shop/catalog` returns normalized `entries` plus a `revision` token for optimistic concurrency on writes.
- `PUT /api/shop/catalog` validates via the same path, then atomically writes `Items/Shop/catalog.yaml` using a temp file + replace.
  - Clients may send optional `expected_revision`.
  - If `expected_revision` does not match current catalog revision, save is rejected with HTTP `409` instead of overwriting newer host state.

Both endpoints enforce the same strict catalog rules used by the read path.

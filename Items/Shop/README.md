# Shop Catalog Overlay

`Items/Shop/` stores **shop-facing overlay metadata** for item listings.

## Purpose

Shop files do **not** redefine item behavior. They only describe:

- whether an item is sold (`enabled`)
- how it is grouped in the shop UI (`shop_category`)
- what it costs (`price`)
- optional stock controls (`stock.limit`, `stock.sold`)

## Source of truth split

- Item-definition YAMLs in `Items/Weapons/`, `Items/Armor/`, `Items/Magic_Items/`, `Items/Consumables/`, and `Items/Gear/` remain the source of truth for item rules/behavior.
- Shop catalog YAML in `Items/Shop/` is the source of truth for sellability/category/price metadata.

Later loader/API code should join shop catalog entries to item definitions by `item_id` + `item_bucket`.

## Supported buckets

`item_bucket` must be one of: `weapon`, `armor`, `magic_item`, `consumable`, `gear`.

## Catalog generation

Use `scripts/build_shop_catalog.py` to generate or refresh `catalog.yaml` from all definition files.
New entries are added as `enabled: false` so the DM controls what goes live. Existing entries
(same `item_bucket` + `item_id`) are preserved with their original prices/stock/enabled state.

```
python scripts/build_shop_catalog.py --dry-run   # preview changes
python scripts/build_shop_catalog.py              # write catalog.yaml
```

## Admin API support (`/shop_admin` + backend)

The backend exposes unprotected admin-facing catalog write helpers used by the current `/shop_admin` LAN UI:

- `POST /api/shop/catalog/validate` validates a proposed catalog payload **in memory** and returns normalized entries for preview.
- `GET /api/shop/catalog` returns normalized `entries` plus a `revision` token for optimistic concurrency on writes.
  - Supports query params: `q` (text search), `bucket`, `category`, `tier`, `include_disabled`.
  - Response also includes `total` (count of returned entries).
- `PUT /api/shop/catalog` validates via the same path, then atomically writes `Items/Shop/catalog.yaml` using a temp file + replace.
  - Clients may send optional `expected_revision`.
  - If `expected_revision` does not match current catalog revision, save is rejected with HTTP `409` instead of overwriting newer host state.

Both endpoints enforce the same strict catalog rules used by the read path.

## Stock model

Each catalog entry may include:

```yaml
stock:
  limit: 10
  sold: 3
```

- `limit`: max total purchasable quantity (omit/null for unlimited stock)
- `sold`: count already purchased (defaults to `0`)
- remaining stock is derived as `limit - sold`

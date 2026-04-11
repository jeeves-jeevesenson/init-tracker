# Composite Ship Blueprint Pipeline (v1)

This folder contains the ship content pipeline split into:

- `source_tiled/` — authoring-time Tiled export JSON (`*.tiled.json`)
- `blueprints/` — normalized runtime blueprints (`composite_ship_blueprint_v1`)

Runtime only reads normalized files. Tiled is **not** required at runtime.

## Runtime render metadata (v1 seam)

`render` supports deterministic fallback rendering:

1. asset-backed render when valid metadata + asset are available
2. exact hull cell-union polygon render fallback
3. optional debug cell overlay (toggle in map UI)

Supported normalized `render` fields:

- `style` (`polygon`, `asset_or_polygon`, etc.; currently compatibility-friendly)
- `fallback_style` (defaults to `polygon`)
- `base_image_key` (runtime asset lookup key)
- `base_image_path` (optional direct asset path)
- `deck_texture_key` (runtime lookup key for hull-clipped deck texture; defaults to `ship_deck_wood`)
- `deck_texture_path` (optional direct texture path override)
- `image_anchor` (`center`, `n`, `s`, `e`, `w`, `ne`, `nw`, `se`, `sw`)
- `image_offset_col` / `image_offset_row`
- `facing_assets` object keyed by facing (`0`, `90`, `180`, `270`) for per-facing overrides

## Importer

Run:

```bash
python scripts/import_tiled_ship_blueprints.py
```

Optional:

- `--source-dir` to point at another source folder
- `--output-dir` to point at another normalized output folder
- `--ids sloop brig` to import specific ships

## Tiled source conventions (first pass)

Required root fields:

- `id`, `width`, `height`
- `ship` metadata object
- `layers`

Required layer:

- `hull` layer with either:
  - `cells: [{col,row}, ...]`, or
  - `data` tile array with non-zero entries treated as hull cells

Optional object layers:

- `fixtures`
- `components`
- `weapon_hardpoints`
- `boarding_points`
- `deck_regions`

Objects should include `id`, `name`, `kind` (or `type`) and `col`/`row`.

### `deck_regions` object convention

Each object normalizes to one canonical runtime deck region:

- `id` (required, unique per ship)
- `label` or `name` (display text)
- `category` (optional semantic tag such as `helm`, `main_deck`, `forecastle`, `hold`, etc.)
- region shape via either:
  - `cells: [{col,row}, ...]`, or
  - rectangle-style `col`, `row`, `width`, `height` (runtime expands to cells)
- optional `render_hint` object:
  - `label_priority` (integer)
  - `overlay_style` (string)

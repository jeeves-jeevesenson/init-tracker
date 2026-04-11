# Composite Ship Blueprint Pipeline (v1)

This folder contains the ship content pipeline split into:

- `source_tiled/` — authoring-time Tiled export JSON (`*.tiled.json`)
- `blueprints/` — normalized runtime blueprints (`composite_ship_blueprint_v1`)

Runtime only reads normalized files. Tiled is **not** required at runtime.

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

Objects should include `id`, `name`, `kind` (or `type`) and `col`/`row`.

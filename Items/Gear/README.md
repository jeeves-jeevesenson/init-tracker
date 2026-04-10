# Gear YAML Schema (Draft)

Use one YAML file per mundane gear item in this directory.

```yaml
format_version: 1
id: rope_hempen_50_feet
name: Rope, Hempen (50 feet)
type: gear
kind: gear
category: adventuring_gear
subtype: standard_gear
cost:
  gp: 1
weight_lb: 10
description: A sturdy length of hempen rope.
stackable: false
```

## Purpose

`Items/Gear/` is for non-weapon, non-armor, non-magic, non-consumable item definitions such as:

- adventuring gear
- tools
- ammunition bundles
- equipment packs
- mounts and vehicles
- other mundane shop goods

These are definition files, not player-owned inventory instances.

## Notes

- `stackable: true` is optional and should only be used for items that should collapse into one inventory stack when bought repeatedly.
- `cost` may use `gp`, `sp`, and `cp`.
- Descriptive stubs are acceptable; not every mundane item needs custom automation.

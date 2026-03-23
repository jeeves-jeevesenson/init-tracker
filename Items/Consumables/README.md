# Consumables YAML Schema (Draft)

## Primary format: one file per consumable

Use one YAML file per consumable in this directory. The filename should match the id:

- `healing_potion.yaml` → `id: healing_potion`

```yaml
format_version: 1
id: healing_potion
name: Healing Potion
type: consumable
consumable_type: potion
subtype: healing
description: Restores hit points when consumed.
effect_hint: Heal 2d4 + 2 HP.
```

## Purpose

Files in `Items/Consumables/` define catalog items that can be offered by future shop/inventory flows.
These are item definitions, not player-owned inventory instances.

## How to add a new consumable

1. Create `Items/Consumables/<consumable_id>.yaml`.
2. Set `id: <consumable_id>` in the file.
3. Add core fields (`name`, `type`, and `consumable_type` or `category`).
4. Add optional fields (`subtype`, `description`, `effect_hint`) as needed.

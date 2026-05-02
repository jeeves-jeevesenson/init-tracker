# Monster Capability Coverage Report

## Overview
This report summarizes the results of the monster-control pass to broaden normalized capability coverage.

- **Total Overlays Generated:** 16 (including variants)
- **Primary Source:** dnd5eapi (preferred for structure)
- **Secondary Source:** Open5e (fallback)

## Monster Coverage Summary

| Slug | Name | Caps | Exec | Save | Rech | Status |
|------|------|------|------|------|------|--------|
| adult-red-dragon | Adult Red Dragon | 10 | 6 | 3 | 1 | **Safe to use** |
| archmage | Archmage | 3 | 1 | 0 | 0 | **Display-only spells** |
| bandit | Bandit | 2 | 2 | 0 | 0 | **Safe to use** |
| bugbear-warrior | Bugbear | 4 | 2 | 0 | 0 | **Safe to use** |
| cultist | Cultist | 2 | 1 | 0 | 0 | **Safe to use** |
| goblin-warrior | Goblin | 3 | 2 | 0 | 0 | **Safe to use** |
| kobold-warrior | Kobold | 4 | 2 | 0 | 0 | **Safe to use** |
| ogre | Ogre | 2 | 2 | 0 | 0 | **Safe to use** |
| orc | Orc | 3 | 2 | 0 | 0 | **Safe to use** |
| skeleton | Skeleton | 2 | 2 | 0 | 0 | **Safe to use** |
| troll | Troll | 5 | 2 | 0 | 0 | **Safe to use** |
| wolf | Wolf | 3 | 1 | 0 | 0 | **Safe to use** |
| zombie | Zombie | 2 | 1 | 0 | 0 | **Safe to use** |

## Key Improvements
- **Save Ability Support:** Monsters like the Adult Red Dragon now have executable save DCs and damage (Fire Breath, Wing Attack).
- **Recharge Mechanics:** Recharge metadata is now extracted (e.g., Fire Breath 5-6).
- **Legacy Matching:** Added variant slugs (e.g., `goblin-warrior`) to match existing `Monsters/*.yaml` filenames.
- **Range/Reach Extraction:** Melee reach and ranged attack distances are now extracted where possible.

## Known Limitations
- **Multiattack:** Still display-only (composite actions not yet executable).
- **Spellcasting:** Display-only in this pass.
- **Conditions:** Not yet automated.

## How to Regenerate
```bash
./.venv/bin/python3 scripts/import/monster_capability_import.py
```

## Inventory Audit
```bash
./.venv/bin/python3 scripts/audit/monster_capability_inventory.py
```

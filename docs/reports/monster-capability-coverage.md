# Monster Capability Coverage Report

## Overview
This report summarizes the results of the monster-control pass to broaden normalized capability coverage.

- **Total Overlays Generated:** 16 (including variants)
- **Primary Source:** dnd5eapi (preferred for structure)
- **Secondary Source:** Open5e (fallback)

## Monster Coverage Summary

| Slug | Name | Caps | Exec | Save | Rech | Comp | Ride | Status |
|------|------|------|------|------|------|------|------|--------|
| adult-red-dragon | Adult Red Dragon | 10 | 6 | 3 | 1 | 1 | 2 | **Multi-target Assisted** |
| archmage | Archmage | 3 | 1 | 0 | 0 | 0 | 0 | **Display-only spells** |
| bandit | Bandit | 2 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| bugbear-warrior | Bugbear | 4 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| cultist | Cultist | 2 | 1 | 0 | 0 | 0 | 0 | **Safe to use** |
| goblin-warrior | Goblin | 3 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| kobold-warrior | Kobold | 4 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| ogre | Ogre | 2 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| orc | Orc | 3 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| skeleton | Skeleton | 2 | 2 | 0 | 0 | 0 | 0 | **Safe to use** |
| troll | Troll | 5 | 2 | 0 | 0 | 1 | 0 | **Assisted Multiattack** |
| wolf | Wolf | 3 | 1 | 0 | 0 | 0 | 1 | **Assisted Prone** |
| zombie | Zombie | 2 | 1 | 0 | 0 | 0 | 0 | **Safe to use** |

## Key Improvements
- **Condition Rider Support:** Extract common riders (Prone, Frightened, Grappled) and allow DM-assisted application/removal.
- **Assisted Multiattack Support:** Multiattack (Composite) actions are now executable via sequential child buttons.
- **Save Ability Support:** Monsters like the Adult Red Dragon now have executable save DCs and damage (Fire Breath, Wing Attack).
- **Manual Multi-Target Resolution:** Save/area actions expose DM-selected multi-target rows with fail/success/no-effect/manual outcomes and explicit apply-damage/apply-effects controls.
- **Recharge Mechanics:** Recharge metadata is now extracted (e.g., Fire Breath 5-6).
- **Legacy Matching:** Added variant slugs (e.g., `goblin-warrior`) to match existing `Monsters/*.yaml` filenames.
- **Range/Reach Extraction:** Melee reach and ranged attack distances are now extracted where possible.

## Known Limitations
- **Condition Riders:** DM-controlled only; failed-save riders can be explicitly applied through multi-target resolution, but there is no implicit auto-application.
- **Multiattack:** "Assisted sequential" means DM clicks each child attack; no single-click full automation yet.
- **Spellcasting:** Display-only in this pass.
- **AoE Targeting:** Manual target selection only; no map-template geometry detection.

## How to Regenerate
```bash
./.venv/bin/python3 scripts/importers/monster_capability_import.py
```

## Inventory Audit
```bash
./.venv/bin/python3 scripts/audit/monster_capability_inventory.py
```

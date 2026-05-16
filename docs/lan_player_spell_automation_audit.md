# LAN Player Spell Automation Audit

This document tracks the automation status of spells for player characters in the LAN client.
High priority is given to spells currently prepared or known by active players.

## Player Spells Audit Table

| Player | Spell | Level | Source Status | LAN Visibility | Automation Status | Automation Kind | Evidence | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Eldramar | Fire Bolt | 0 | YAML + Lib | Visible | Complete | Attack | User Note | |
| Eldramar | Toll the Dead | 0 | YAML + Lib | Visible | Complete | Save (Wis) | | |
| Eldramar | Chill Touch | 0 | YAML + Lib | Visible | Complete | Attack | | |
| Eldramar | Eldritch Blast | 0 | YAML + Lib | Visible | Complete | Attack | | |
| Eldramar | Mage Hand | 0 | YAML + Lib | Visible | Manual | Utility | | |
| Eldramar | Message | 0 | YAML + Lib | Visible | Manual | Utility | | |
| Eldramar | Shatter | 2 | YAML + Lib | Visible | Partial | AOE Save (Con) | User Note | Latency issues reported. |
| Eldramar | Fireball | 3 | YAML + Lib | Visible | Complete | AOE Save (Dex) | | |
| Eldramar | Counterspell | 3 | YAML + Lib | Visible | Manual | Reaction | | |
| Eldramar | Haste | 3 | YAML + Lib | Visible | Partial | Buff | | Concentration panel desync? |
| Eldramar | Wall of Fire | 4 | YAML + Lib | Visible | Partial | AOE Save (Dex) | | Persistent AOE. |
| Eldramar | Banishment | 4 | YAML + Lib | Visible | Partial | Save (Cha) | | |
| Eldramar | Greater Invisibility | 4 | YAML + Lib | Visible | Partial | Buff | | Concentration. |
| Eldramar | Wall of Force | 5 | YAML + Lib | Visible | Manual | Utility | | Persistent AOE. |
| Eldramar | Bigby's Hand | 5 | YAML + Lib | Visible | Partial | Utility/Attack | | Concentration. |
| Eldramar | Summon Construct | 4 | YAML + Lib | Visible | Partial | Summon | | |
| Eldramar | Disintegrate | 6 | YAML + Lib | Visible | Complete | Save (Dex) | | |
| Eldramar | Otto's Irresistible Dance | 6 | YAML + Lib | Visible | Partial | Condition | | |
| Eldramar | Create Undead | 6 | YAML + Lib | Visible | Partial | Summon | | |
| Stihiya | Toll the Dead | 0 | YAML + Lib | Visible | Complete | Save (Wis) | | |
| Stihiya | Sacred Flame | 0 | YAML + Lib | Visible | Complete | Save (Dex) | | |
| Stihiya | Spare the Dying | 0 | YAML + Lib | Visible | Manual | Healing | | |
| Stihiya | Guidance | 0 | YAML + Lib | Visible | Manual | Buff | | |
| Stihiya | Mending | 0 | YAML + Lib | Visible | Manual | Utility | | |
| Stihiya | Healing Word | 1 | YAML + Lib | Visible | Complete | Healing | | |
| Stihiya | Thunderwave | 1 | YAML + Lib | Visible | Complete | AOE Save (Con) | User Note | Push and concentration save worked. |
| Stihiya | Guiding Bolt | 1 | YAML + Lib | Visible | Complete | Attack | | |
| Stihiya | Cure Wounds | 1 | YAML + Lib | Visible | Complete | Healing | | |
| Stihiya | Inflict Wounds | 1 | YAML + Lib | Visible | Complete | Attack | | |
| Stihiya | Prayer of Healing | 2 | YAML + Lib | Visible | Complete | Healing | | |
| Stihiya | Lesser Restoration | 2 | YAML + Lib | Visible | Manual | Utility | | |
| Stihiya | Find Traps | 2 | YAML + Lib | Visible | Manual | Utility | | |
| Stihiya | Shatter | 2 | YAML + Lib | Visible | Partial | AOE Save (Con) | | |
| Stihiya | Revivify | 3 | YAML + Lib | Visible | Manual | Healing | | |
| Stihiya | Dispel Magic | 3 | YAML + Lib | Visible | Manual | Utility | | |
| Stihiya | Bestow Curse | 3 | YAML + Lib | Visible | Partial | Save (Wis) | | |
| Stihiya | Call Lightning | 3 | YAML + Lib | Visible | Partial | Persistent AOE | | Special case: repeatable action. |
| Stihiya | Sleet Storm | 3 | YAML + Lib | Visible | Partial | Persistent AOE | User Note | Concentration panel desync suspected. |
| Stihiya | Flame Strike | 5 | YAML + Lib | Visible | Complete | AOE Save (Dex) | | |
| Stihiya | Harm | 6 | YAML + Lib | Visible | Complete | Save (Con) | | |
| Stihiya | Destructive Wave | 5 | Missing from Lib class | Hidden | Complete | AOE Save (Con) | User Note | Missing from Cleric list in lib. |
| Vicnor | Eldritch Blast | 0 | YAML + Lib | Visible | Complete | Attack | | |
| Vicnor | Poison Spray | 0 | YAML + Lib | Visible | Complete | Save (Con) | | |
| Vicnor | Prestidigitation | 0 | YAML + Lib | Visible | Manual | Utility | | |
| Vicnor | Chaos Bolt (Izzet) | 1 | YAML + Lib | Visible | Complete | Attack | | |
| Vicnor | Hellish Rebuke | 1 | YAML + Lib | Visible | Complete | Reaction Save (Dex)| | |
| Vicnor | Hypnotic Pattern | 3 | YAML + Lib | Visible | Partial | AOE Save (Wis) | | |
| Vicnor | Dimension Door | 4 | YAML + Lib | Visible | Manual | Utility | | |
| Vicnor | Phantasmal Killer | 4 | YAML + Lib | Visible | Complete | Save (Wis) | User Note | Model fully automated spell. |
| Vicnor | Disguise Self | 1 | YAML + Lib | Visible | Manual | Utility | | |
| Vicnor | Absorb Elements | 1 | YAML + Lib | Visible | Manual | Reaction | | |
| Vicnor | Silent Image | 1 | YAML + Lib | Visible | Manual | Utility | | |
| Fred | Armor of Agathys | 1 | YAML + Lib | Visible | Partial | Buff | | |
| Fred | Cloud of Daggers | 2 | YAML + Lib | Visible | Partial | Persistent AOE | | |
| Fred | Tasha's Hideous Laughter | 1 | YAML + Lib | Visible | Partial | Save (Wis) | User Note | Weird label reported. |

## Key Findings & Actions

1. **Shatter Latency:** AOE spells like Shatter take a long time to resolve. Need to investigate backend `cast_aoe` and `spell_target_request` performance.
2. **Destructive Wave:** Missing from Cleric class list in `Spells/destructive-wave.yaml`. Action: Add `cleric` to the list.
3. **Sleet Storm / Concentration:** Concentration saves work, but the UI panel might not be updating correctly.
4. **Tasha's Hideous Laughter:** Weird dropdown label. Action: Stabilize summary label in `assets/web/lan/index.html`.
5. **Call Lightning:** Requires persistent AOE + repeatable Magic action. Mark as WIP/Special-case.
6. **Unarmed Strike:** Old Man (and others) need a reliable Unarmed Strike fallback when no weapon is equipped/configured.

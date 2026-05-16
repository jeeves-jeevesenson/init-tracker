# LAN Player Spell Automation Audit

This document tracks the automation status of spells for player characters in the LAN client.
High priority is given to spells currently prepared or known by active players.

## Player Spells Audit Table

| Player | Spell | Level | Automation Status | Game Ready? | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Eldramar | Fire Bolt | 0 | Complete | ✅ Yes | Attack |
| Eldramar | Toll the Dead | 0 | Complete | ✅ Yes | Save (Wis) |
| Eldramar | Chill Touch | 0 | Complete | ✅ Yes | Attack |
| Eldramar | Eldritch Blast | 0 | Complete | ✅ Yes | Attack |
| Eldramar | Mage Hand | 0 | Manual | ✅ Yes | Manual tracking needed |
| Eldramar | Message | 0 | Manual | ✅ Yes | Manual tracking needed |
| Eldramar | Shatter | 2 | Partial | ⚠️ Caution | Latency fix applied; test in smoke |
| Eldramar | Fireball | 3 | Complete | ✅ Yes | AOE Save (Dex) |
| Eldramar | Counterspell | 3 | Manual | ✅ Yes | Reaction; manual tracking |
| Eldramar | Haste | 3 | Partial | ⚠️ Caution | Concentration panel might desync |
| Eldramar | Wall of Fire | 4 | Partial | ⚠️ Caution | Persistent AOE |
| Eldramar | Banishment | 4 | Partial | ⚠️ Caution | Save (Cha) |
| Eldramar | Greater Invisibility | 4 | Partial | ⚠️ Caution | Concentration |
| Eldramar | Wall of Force | 5 | Manual | ✅ Yes | Manual tracking needed |
| Eldramar | Bigby's Hand | 5 | Partial | ⚠️ Caution | Concentration |
| Eldramar | Summon Construct | 4 | Partial | ⚠️ Caution | DM spawn only? |
| Eldramar | Disintegrate | 6 | Complete | ✅ Yes | Save (Dex) |
| Eldramar | Otto's Dance | 6 | Partial | ⚠️ Caution | Condition tracking |
| Eldramar | Create Undead | 6 | Partial | ⚠️ Caution | Summon |
| Stihiya | Toll the Dead | 0 | Complete | ✅ Yes | Save (Wis) |
| Stihiya | Sacred Flame | 0 | Complete | ✅ Yes | Save (Dex) |
| Stihiya | Spare the Dying | 0 | Manual | ✅ Yes | Healing |
| Stihiya | Guidance | 0 | Manual | ✅ Yes | Buff |
| Stihiya | Mending | 0 | Manual | ✅ Yes | Utility |
| Stihiya | Healing Word | 1 | Complete | ✅ Yes | Healing |
| Stihiya | Thunderwave | 1 | Complete | ✅ Yes | Push and concentration save verified |
| Stihiya | Guiding Bolt | 1 | Complete | ✅ Yes | Attack |
| Stihiya | Cure Wounds | 1 | Complete | ✅ Yes | Healing |
| Stihiya | Inflict Wounds | 1 | Complete | ✅ Yes | Attack |
| Stihiya | Prayer of Healing | 2 | Complete | ✅ Yes | Healing |
| Stihiya | Lesser Restoration | 2 | Manual | ✅ Yes | Utility |
| Stihiya | Find Traps | 2 | Manual | ✅ Yes | Utility |
| Stihiya | Shatter | 2 | Partial | ⚠️ Caution | Latency fix applied |
| Stihiya | Revivify | 3 | Manual | ✅ Yes | Healing |
| Stihiya | Dispel Magic | 3 | Manual | ✅ Yes | Utility |
| Stihiya | Bestow Curse | 3 | Partial | ⚠️ Caution | Save (Wis) |
| Stihiya | Call Lightning | 3 | Partial | ❌ No | Special case: repeatable action |
| Stihiya | Sleet Storm | 3 | Partial | ⚠️ Caution | Concentration panel fix applied |
| Stihiya | Flame Strike | 5 | Complete | ✅ Yes | AOE Save (Dex) |
| Stihiya | Harm | 6 | Complete | ✅ Yes | Save (Con) |
| Stihiya | Destructive Wave | 5 | Complete | ✅ Yes | Added to Cleric list |
| Vicnor | Eldritch Blast | 0 | Complete | ✅ Yes | Attack |
| Vicnor | Poison Spray | 0 | Complete | ✅ Yes | Save (Con) |
| Vicnor | Prestidigitation | 0 | Manual | ✅ Yes | Utility |
| Vicnor | Chaos Bolt | 1 | Complete | ✅ Yes | Attack |
| Vicnor | Hellish Rebuke | 1 | Complete | ✅ Yes | Reaction Save (Dex) |
| Vicnor | Hypnotic Pattern | 3 | Partial | ⚠️ Caution | AOE Save (Wis) |
| Vicnor | Dimension Door | 4 | Manual | ✅ Yes | Utility |
| Vicnor | Phantasmal Killer | 4 | Complete | ✅ Yes | Model automated spell |
| Vicnor | Disguise Self | 1 | Manual | ✅ Yes | Utility |
| Vicnor | Absorb Elements | 1 | Manual | ✅ Yes | Reaction |
| Vicnor | Silent Image | 1 | Manual | ✅ Yes | Utility |
| Fred | Armor of Agathys | 1 | Partial | ✅ Yes | Buff |
| Fred | Cloud of Daggers | 2 | Partial | ⚠️ Caution | Persistent AOE |
| Fred | Tasha's Laughter | 1 | Partial | ✅ Yes | Label fix applied |

## Key Findings & Actions

1. **Shatter Latency:** Fixed. Redundant broadcasts per target removed in `dnd_initative_tracker.py`.
2. **Destructive Wave:** Fixed. Added `cleric` to `Spells/destructive-wave.yaml`.
3. **Sleet Storm / Concentration:** Fixed. UI now shows "Active" concentration even if spell name is missing. HUD updates on static data arrival.
4. **Tasha's Hideous Laughter:** Fixed. Dropdown label stabilized in `assets/web/lan/index.html`.
5. **Call Lightning:** **NOT READY.** Requires persistent AOE + repeatable Magic action.
6. **Unarmed Strike:** Fixed. Fallback added for characters without configured weapons.
7. **Vicnor .45 Pistol:** Fixed. Now surfaced from `attacks.weapons`.

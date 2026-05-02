#!/usr/bin/env python3
import os
import yaml
import re
import json
from typing import Dict, List, Any

# Paths
MONSTERS_DIR = "Monsters"
REPORT_DIR = "docs/reports"
REPORT_PATH = os.path.join(REPORT_DIR, "monster-capability-audit.md")

# Regex for markers
MARKERS = {
    "hit": re.compile(r"\{@hit\s+([-+]?\d+)\}"),
    "damage": re.compile(r"\{@damage\s+([^}]+)\}"),
    "dc": re.compile(r"\{@dc\s+(\d+)\}"),
    "recharge": re.compile(r"\{@recharge(?:\s+(\d+))?\}"),
    "condition": re.compile(r"\{@condition\s+([^}]+)\}"),
    "spell": re.compile(r"\{@spell\s+([^}]+)\}"),
    "multiattack": re.compile(r"multiattack", re.IGNORECASE),
}

def audit_monsters():
    stats = {
        "total": 0,
        "with_actions": 0,
        "empty_actions": 0,
        "with_traits": 0,
        "empty_traits": 0,
        "with_legendary": 0,
        "empty_legendary": 0,
        "with_bonus": 0,
        "with_reactions": 0,
        "spellcasting_text": 0,
        "recharge_text": 0,
        "save_dc_text": 0,
        "attack_damage_text": 0,
        "multiattack_text": 0,
        "condition_text": 0,
        "malformed": 0,
    }

    examples = {
        "simple_melee": [],
        "ranged": [],
        "multiattack": [],
        "recharge": [],
        "save_dc": [],
        "legendary": [],
        "spellcaster": [],
        "display_only": [],
    }

    readiness = {
        "executable": 0,
        "partial": 0,
        "display_only": 0,
        "missing_data": 0,
    }

    if not os.path.exists(MONSTERS_DIR):
        print(f"Error: {MONSTERS_DIR} not found.")
        return

    for filename in sorted(os.listdir(MONSTERS_DIR)):
        if not filename.endswith(".yaml"):
            continue
        
        filepath = os.path.join(MONSTERS_DIR, filename)
        stats["total"] += 1
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            stats["malformed"] += 1
            continue

        if not data:
            stats["malformed"] += 1
            continue

        name = data.get("name", filename)
        actions = data.get("actions") or []
        traits = data.get("traits") or []
        legendary = data.get("legendary_actions") or []
        bonus = data.get("bonus_actions") or []
        reactions = data.get("reactions") or []

        if actions: stats["with_actions"] += 1
        else: stats["empty_actions"] += 1

        if traits: stats["with_traits"] += 1
        else: stats["empty_traits"] += 1

        if legendary: stats["with_legendary"] += 1
        else: stats["empty_legendary"] += 1

        if bonus: stats["with_bonus"] += 1
        if reactions: stats["with_reactions"] += 1

        # Content analysis
        full_text = ""
        any_multi = False
        any_recharge = False
        for item_list in [actions, traits, legendary, bonus, reactions]:
            for item in item_list:
                name_field = item.get("name", "")
                desc_field = item.get("desc", "")
                
                if MARKERS["multiattack"].search(name_field):
                    any_multi = True
                if MARKERS["recharge"].search(name_field) or MARKERS["recharge"].search(desc_field):
                    any_recharge = True
                
                full_text += name_field + " " + desc_field + " "

        has_hit = MARKERS["hit"].search(full_text)
        has_damage = MARKERS["damage"].search(full_text)
        has_dc = MARKERS["dc"].search(full_text)
        has_spell = MARKERS["spell"].search(full_text)
        has_cond = MARKERS["condition"].search(full_text)

        if has_hit and has_damage: stats["attack_damage_text"] += 1
        if has_dc: stats["save_dc_text"] += 1
        if any_recharge: stats["recharge_text"] += 1
        if has_spell: stats["spellcasting_text"] += 1
        if any_multi: stats["multiattack_text"] += 1
        if has_cond: stats["condition_text"] += 1

        # Examples
        if any_multi and len(examples["multiattack"]) < 3: examples["multiattack"].append(name)
        if any_recharge and len(examples["recharge"]) < 3: examples["recharge"].append(name)
        if has_dc and len(examples["save_dc"]) < 3: examples["save_dc"].append(name)
        if legendary and len(examples["legendary"]) < 3: examples["legendary"].append(name)
        if has_spell and len(examples["spellcaster"]) < 3: examples["spellcaster"].append(name)
        
        # Classification
        if has_hit and has_damage and not any_multi and not any_recharge:
            readiness["executable"] += 1
            if len(examples["simple_melee"]) < 3: examples["simple_melee"].append(name)
        elif (has_hit or has_dc or any_recharge or any_multi) and (has_damage or has_cond or any_multi):
            readiness["partial"] += 1
        elif not actions and not traits:
            readiness["missing_data"] += 1
        else:
            readiness["display_only"] += 1
            if len(examples["display_only"]) < 3: examples["display_only"].append(name)

    # Generate Report
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Monster Capability Audit Report\n\n")
        f.write("## Summary Statistics\n\n")
        f.write(f"- **Total Monsters:** {stats['total']}\n")
        f.write(f"- **With Actions:** {stats['with_actions']} ({stats['empty_actions']} empty)\n")
        f.write(f"- **With Traits:** {stats['with_traits']} ({stats['empty_traits']} empty)\n")
        f.write(f"- **With Legendary Actions:** {stats['with_legendary']} ({stats['empty_legendary']} empty)\n")
        f.write(f"- **With Bonus Actions:** {stats['with_bonus']}\n")
        f.write(f"- **With Reactions:** {stats['with_reactions']}\n")
        f.write(f"- **Malformed/Unreadable:** {stats['malformed']}\n\n")

        f.write("## Content Analysis (Text-based Detection)\n\n")
        f.write(f"- **Attack/Damage ({{@hit}} + {{@damage}}):** {stats['attack_damage_text']}\n")
        f.write(f"- **Save DC ({{@dc}}):** {stats['save_dc_text']}\n")
        f.write(f"- **Recharge ({{@recharge}}):** {stats['recharge_text']}\n")
        f.write(f"- **Multiattack Mentioned:** {stats['multiattack_text']}\n")
        f.write(f"- **Spellcasting ({{@spell}}):** {stats['spellcasting_text']}\n")
        f.write(f"- **Conditions ({{@condition}}):** {stats['condition_text']}\n\n")

        f.write("## Backend Readiness Classification\n\n")
        f.write(f"- **Likely Executable Simple Attack:** {readiness['executable']}\n")
        f.write(f"- **Partially Parseable:** {readiness['partial']}\n")
        f.write(f"- **Display-Only:** {readiness['display_only']}\n")
        f.write(f"- **Missing Critical Action Data:** {readiness['missing_data']}\n\n")

        f.write("## Representative Examples\n\n")
        for cat, names in examples.items():
            f.write(f"- **{cat.replace('_', ' ').title()}:** {', '.join(names) if names else 'None'}\n")

    print(f"Audit complete. Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    audit_monsters()

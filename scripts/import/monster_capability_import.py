#!/usr/bin/env python3
import json
import yaml
import os
from typing import Dict, List, Any

# Paths
SAMPLE_DATA_DIR = "docs/reports/monster-source-samples"
OUTPUT_DIR = "monster_capabilities/samples"
LEGACY_DIR = "Monsters"

def normalize_o5e_action(action: Dict[str, Any], monster_slug: str) -> Dict[str, Any]:
    """Normalize an Open5e V2 action object."""
    cap = {
        "id": action.get("name", "action").lower().replace(" ", "-"),
        "name": action.get("name"),
        "type": "action",
        "executable": False,
        "desc": action.get("desc"),
        "action_type": "utility",
        "mechanics": {}
    }

    # Determine type
    o5e_type = action.get("action_type", "ACTION")
    if o5e_type == "LEGENDARY_ACTION":
        cap["type"] = "legendary_action"
        cap["cost"] = action.get("legendary_action_cost", 1)
    elif o5e_type == "REACTION":
        cap["type"] = "reaction"
    
    # Check for attacks
    attacks = action.get("attacks", [])
    if attacks:
        atk = attacks[0]
        cap["executable"] = True
        cap["action_type"] = "melee_attack" if atk.get("reach") else "ranged_attack"
        cap["mechanics"] = {
            "attack_bonus": atk.get("to_hit_mod"),
            "damage": []
        }
        if atk.get("damage_die_count"):
            formula = f"{atk.get('damage_die_count')}{atk.get('damage_die_type', 'D6')}"
            if atk.get("damage_bonus"):
                formula += f"+{atk.get('damage_bonus')}"
            
            damage_type = "unspecified"
            if atk.get("extra_damage_type"):
                damage_type = atk.get("extra_damage_type", {}).get("key", "unspecified")
            
            cap["mechanics"]["damage"].append({
                "formula": formula.lower(),
                "type": damage_type
            })

    # Multiattack detection
    if "multiattack" in cap["name"].lower():
        cap["action_type"] = "composite"
        cap["executable"] = False # Multiattack logic is complex to automate without better links
    
    # Recharge detection
    if "recharge" in cap["name"].lower():
        cap["recharge"] = 5 # Default 5-6 if not specified

    return cap

def normalize_dnd5eapi_action(action: Dict[str, Any], monster_slug: str) -> Dict[str, Any]:
    """Normalize a dnd5eapi action object."""
    cap = {
        "id": action.get("name", "action").lower().replace(" ", "-"),
        "name": action.get("name"),
        "type": "action",
        "executable": False,
        "desc": action.get("desc"),
        "action_type": "utility",
        "mechanics": {}
    }

    # Check for recharge
    usage = action.get("usage")
    if usage and usage.get("type") == "recharge on roll":
        cap["recharge"] = usage.get("min_value", 5)

    # Check for save ability
    dc = action.get("dc")
    if dc:
        cap["executable"] = True
        cap["action_type"] = "save_ability"
        cap["mechanics"] = {
            "save_dc": dc.get("dc_value"),
            "save_ability": dc.get("dc_type", {}).get("index", "dex").lower(),
            "damage": []
        }
        # Success type
        if dc.get("success_type") == "half":
            cap["mechanics"]["on_save"] = "half"
        else:
            cap["mechanics"]["on_save"] = "none"

        # Damage for save
        for dmg in action.get("damage", []):
            if dmg.get("damage_dice"):
                cap["mechanics"]["damage"].append({
                    "formula": dmg.get("damage_dice").lower(),
                    "type": dmg.get("damage_type", {}).get("index", "unspecified")
                })

    # Check for attacks (if not already a save_ability)
    elif action.get("attack_bonus") is not None or action.get("damage"):
        cap["executable"] = True
        desc_lower = action.get("desc", "").lower()
        cap["action_type"] = "melee_attack" if "reach" in desc_lower else "ranged_attack"
        cap["mechanics"] = {
            "attack_bonus": action.get("attack_bonus"),
            "damage": []
        }
        for dmg in action.get("damage", []):
            if dmg.get("damage_dice"):
                cap["mechanics"]["damage"].append({
                    "formula": dmg.get("damage_dice").lower(),
                    "type": dmg.get("damage_type", {}).get("index", "unspecified")
                })
        
        # Range/Reach extraction from desc if possible
        if "reach" in desc_lower:
            import re
            reach_match = re.search(r"reach (\d+) ft", desc_lower)
            if reach_match:
                cap["mechanics"]["reach"] = int(reach_match.group(1))
        if "range" in desc_lower:
            import re
            range_match = re.search(r"range (\d+)/(\d+) ft", desc_lower)
            if range_match:
                cap["mechanics"]["range"] = int(range_match.group(1))
                cap["mechanics"]["long_range"] = int(range_match.group(2))

    # Multiattack detection
    if "multiattack" in cap["name"].lower():
        cap["action_type"] = "composite"
        cap["executable"] = False

    return cap

def import_monster(source_slug: str, target_slug: str = None):
    if not target_slug:
        target_slug = source_slug
        
    o5e_path = os.path.join(SAMPLE_DATA_DIR, f"{source_slug}-open5e.json")
    dnd_path = os.path.join(SAMPLE_DATA_DIR, f"{source_slug}-dnd5eapi.json")
    
    data = {}
    source_name = "Unknown"
    
    if os.path.exists(dnd_path):
        with open(dnd_path, "r") as f:
            data = json.load(f)
        source_name = "dnd5eapi"
    elif os.path.exists(o5e_path):
        with open(o5e_path, "r") as f:
            data = json.load(f)
        source_name = data.get("document", {}).get("name", "Open5e")
    else:
        print(f"Skipping {source_slug}, no sample found.")
        return

    norm = {
        "name": data.get("name"),
        "slug": target_slug,
        "source": source_name,
        "license": "CC-BY-4.0",
        "capabilities": []
    }

    if source_name == "dnd5eapi":
        for action in data.get("actions", []):
            norm["capabilities"].append(normalize_dnd5eapi_action(action, target_slug))
        for action in data.get("legendary_actions", []):
            cap = normalize_dnd5eapi_action(action, target_slug)
            cap["type"] = "legendary_action"
            norm["capabilities"].append(cap)
        for trait in data.get("special_abilities", []):
            # Try to normalize traits if they have actions/usage
            cap = {
                "id": trait.get("name", "trait").lower().replace(" ", "-"),
                "name": trait.get("name"),
                "type": "trait",
                "executable": False,
                "desc": trait.get("desc")
            }
            norm["capabilities"].append(cap)
    else:
        # Fallback to O5E normalization
        for action in data.get("actions", []):
            norm["capabilities"].append(normalize_o5e_action(action, target_slug))
        for trait in data.get("traits", []):
            norm["capabilities"].append({
                "id": trait.get("name", "trait").lower().replace(" ", "-"),
                "name": trait.get("name"),
                "type": "trait",
                "executable": False,
                "desc": trait.get("desc")
            })

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{target_slug}.yaml")
    with open(out_path, "w") as f:
        yaml.dump(norm, f, sort_keys=False)
    print(f"Generated {out_path}")

def import_samples():
    targets = [
        ("skeleton", "skeleton"),
        ("goblin", "goblin"),
        ("goblin", "goblin-warrior"),
        ("zombie", "zombie"),
        ("wolf", "wolf"),
        ("bandit", "bandit"),
        ("cultist", "cultist"),
        ("orc", "orc"),
        ("kobold", "kobold"),
        ("kobold", "kobold-warrior"),
        ("bugbear", "bugbear"),
        ("bugbear", "bugbear-warrior"),
        ("ogre", "ogre"),
        ("troll", "troll"),
        ("adult-red-dragon", "adult-red-dragon"),
        ("archmage", "archmage")
    ]
    for source, target in targets:
        import_monster(source, target)

if __name__ == "__main__":
    import_samples()

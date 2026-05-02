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

    # Check for attacks
    if action.get("attack_bonus") is not None or action.get("damage"):
        cap["executable"] = True
        cap["action_type"] = "melee_attack" if "reach" in action.get("desc", "").lower() else "ranged_attack"
        cap["mechanics"] = {
            "attack_bonus": action.get("attack_bonus"),
            "damage": []
        }
        for dmg in action.get("damage", []):
            cap["mechanics"]["damage"].append({
                "formula": dmg.get("damage_dice"),
                "type": dmg.get("damage_type", {}).get("index", "unspecified")
            })

    # Multiattack detection
    if "multiattack" in cap["name"].lower():
        cap["action_type"] = "composite"

    return cap

def import_monster(slug: str):
    o5e_path = os.path.join(SAMPLE_DATA_DIR, f"{slug}-open5e.json")
    dnd_path = os.path.join(SAMPLE_DATA_DIR, f"{slug}-dnd5eapi.json")
    
    data = {}
    source_name = "Unknown"
    
    if os.path.exists(dnd_path):
        with open(dnd_path, "r") as f:
            data = json.load(f)
        source_name = "dnd5eapi"
        is_o5e = False
    elif os.path.exists(o5e_path):
        with open(o5e_path, "r") as f:
            data = json.load(f)
        source_name = data.get("document", {}).get("name", "Open5e")
        is_o5e = True
    else:
        print(f"Skipping {slug}, no sample found.")
        return

    norm = {
        "name": data.get("name"),
        "slug": slug,
        "source": source_name,
        "license": "CC-BY-4.0",
        "capabilities": []
    }

    if source_name == "dnd5eapi":
        for action in data.get("actions", []):
            norm["capabilities"].append(normalize_dnd5eapi_action(action, slug))
        for action in data.get("legendary_actions", []):
            cap = normalize_dnd5eapi_action(action, slug)
            cap["type"] = "legendary_action"
            norm["capabilities"].append(cap)
        for trait in data.get("special_abilities", []):
            norm["capabilities"].append({
                "id": trait.get("name", "trait").lower().replace(" ", "-"),
                "name": trait.get("name"),
                "type": "trait",
                "executable": False,
                "desc": trait.get("desc")
            })
    else:
        # Fallback to O5E normalization
        for action in data.get("actions", []):
            norm["capabilities"].append(normalize_o5e_action(action, slug))
        for trait in data.get("traits", []):
            norm["capabilities"].append({
                "id": trait.get("name", "trait").lower().replace(" ", "-"),
                "name": trait.get("name"),
                "type": "trait",
                "executable": False,
                "desc": trait.get("desc")
            })

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{slug}.yaml")
    with open(out_path, "w") as f:
        yaml.dump(norm, f, sort_keys=False)
    print(f"Generated {out_path}")

def import_samples():
    samples = ["skeleton", "goblin", "adult-red-dragon", "archmage"]
    for s in samples:
        import_monster(s)

if __name__ == "__main__":
    import_samples()

#!/usr/bin/env python3
import os
import yaml
from typing import Dict, List, Any

# Paths
CAPABILITY_DIR = "monster_capabilities"

def audit_inventory():
    inventory = []
    
    if not os.path.exists(CAPABILITY_DIR):
        print(f"Error: {CAPABILITY_DIR} not found.")
        return

    import glob
    pattern = os.path.join(CAPABILITY_DIR, "**", "*.yaml")
    files = sorted(glob.glob(pattern, recursive=True))
    
    print(f"{'Slug':<25} | {'Name':<25} | {'Caps':<5} | {'Exec':<5} | {'Save':<5} | {'Area':<5} | {'Res':<5} | {'Comp':<5} | {'Ride':<5} | {'Spell':<5} | {'Warn':<5}")
    print("-" * 155)
    
    for path in files:
        with open(path, "r") as stream:
            data = yaml.safe_load(stream)
            
            slug = data.get("slug", "???")
            name = data.get("name", "???")
            caps = data.get("capabilities", [])
            
            total = len(caps)
            executable = sum(1 for c in caps if c.get("executable"))
            saves = sum(1 for c in caps if c.get("action_type") == "save_ability")
            areas = sum(1 for c in caps if c.get("mechanics", {}).get("shape"))
            recharges = sum(1 for c in caps if "recharge" in c or c.get("mechanics", {}).get("uses"))
            composite = sum(1 for c in caps if c.get("action_type") == "composite")
            riders = sum(len(c.get("mechanics", {}).get("effects", [])) for c in caps)
            spells = sum(1 for c in caps if c.get("action_type") in ("spellcasting", "spell"))
            warnings = sum(len(c.get("warnings", [])) for c in caps)
            
            print(f"{slug:<25} | {name:<25} | {total:<5} | {executable:<5} | {saves:<5} | {areas:<5} | {recharges:<5} | {composite:<5} | {riders:<5} | {spells:<5} | {warnings:<5}")
            
            inventory.append({
                "slug": slug,
                "name": name,
                "total": total,
                "executable": executable,
                "saves": saves,
                "areas": areas,
                "resources": recharges,
                "composite": composite,
                "riders": riders,
                "spells": spells,
                "warnings": warnings,
            })
            
    return inventory

if __name__ == "__main__":
    audit_inventory()

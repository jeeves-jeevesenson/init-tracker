#!/usr/bin/env python3
import os
import yaml
from typing import Dict, List, Any

# Paths
CAPABILITY_DIR = "monster_capabilities/samples"

def audit_inventory():
    inventory = []
    
    if not os.path.exists(CAPABILITY_DIR):
        print(f"Error: {CAPABILITY_DIR} not found.")
        return

    files = sorted([f for f in os.listdir(CAPABILITY_DIR) if f.endswith(".yaml")])
    
    print(f"{'Slug':<25} | {'Name':<25} | {'Caps':<5} | {'Exec':<5} | {'Save':<5} | {'Rech':<5}")
    print("-" * 100)
    
    for f in files:
        path = os.path.join(CAPABILITY_DIR, f)
        with open(path, "r") as stream:
            data = yaml.safe_load(stream)
            
            slug = data.get("slug", "???")
            name = data.get("name", "???")
            caps = data.get("capabilities", [])
            
            total = len(caps)
            executable = sum(1 for c in caps if c.get("executable"))
            saves = sum(1 for c in caps if c.get("action_type") == "save_ability")
            recharges = sum(1 for c in caps if "recharge" in c)
            
            print(f"{slug:<25} | {name:<25} | {total:<5} | {executable:<5} | {saves:<5} | {recharges:<5}")
            
            inventory.append({
                "slug": slug,
                "name": name,
                "total": total,
                "executable": executable,
                "saves": saves,
                "recharges": recharges
            })
            
    return inventory

if __name__ == "__main__":
    audit_inventory()

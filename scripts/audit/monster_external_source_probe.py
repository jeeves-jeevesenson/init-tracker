#!/usr/bin/env python3
import requests
import json
import os
import sys

# Targets
SAMPLES = [
    {"o5e": "srd_skeleton", "dnd": "skeleton"},
    {"o5e": "srd_goblin", "dnd": "goblin"},
    {"o5e": "srd_zombie", "dnd": "zombie"},
    {"o5e": "srd_wolf", "dnd": "wolf"},
    {"o5e": "srd_bandit", "dnd": "bandit"},
    {"o5e": "srd_cultist", "dnd": "cultist"},
    {"o5e": "srd_orc", "dnd": "orc"},
    {"o5e": "srd_kobold", "dnd": "kobold"},
    {"o5e": "srd_bugbear", "dnd": "bugbear"},
    {"o5e": "srd_ogre", "dnd": "ogre"},
    {"o5e": "srd_troll", "dnd": "troll"},
    {"o5e": "srd_adult-red-dragon", "dnd": "adult-red-dragon"},
    {"o5e": "srd_archmage", "dnd": "archmage"}
]
OPEN5E_URL_V2 = "https://api.open5e.com/v2/creatures/"
DND5EAPI_URL = "https://www.dnd5eapi.co/api/monsters/"

REPORT_DIR = "docs/reports"
SAMPLE_DIR = os.path.join(REPORT_DIR, "monster-source-samples")
REPORT_PATH = os.path.join(REPORT_DIR, "monster-external-source-probe.md")

def probe_sources():
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    report = []
    report.append("# Monster External Source Probe Report\n")
    
    for sample in SAMPLES:
        o5e_key = sample["o5e"]
        dnd_slug = sample["dnd"]
        report.append(f"## Monster: {dnd_slug}\n")
        
        # Open5e V2
        try:
            o5e_res = requests.get(f"{OPEN5E_URL_V2}{o5e_key}/", timeout=10)
            if o5e_res.status_code == 200:
                o5e_data = o5e_res.json()
                sample_file = os.path.join(SAMPLE_DIR, f"{dnd_slug}-open5e.json")
                with open(sample_file, "w") as f:
                    json.dump(o5e_data, f, indent=2)
                report.append(f"- **Open5e (V2):** Success (Saved to `{sample_file}`)\n")
                report.append(f"  - Actions count: {len(o5e_data.get('actions', []))}\n")
            else:
                report.append(f"- **Open5e (V2):** Failed (HTTP {o5e_res.status_code} for {o5e_key})\n")
        except Exception as e:
            report.append(f"- **Open5e (V2):** Error ({str(e)})\n")

        # dnd5eapi
        try:
            dnd_res = requests.get(f"{DND5EAPI_URL}{dnd_slug}/", timeout=10)
            if dnd_res.status_code == 200:
                dnd_data = dnd_res.json()
                sample_file = os.path.join(SAMPLE_DIR, f"{dnd_slug}-dnd5eapi.json")
                with open(sample_file, "w") as f:
                    json.dump(dnd_data, f, indent=2)
                report.append(f"- **dnd5eapi:** Success (Saved to `{sample_file}`)\n")
                report.append(f"  - Actions count: {len(dnd_data.get('actions', []))}\n")
            else:
                report.append(f"- **dnd5eapi:** Failed (HTTP {dnd_res.status_code})\n")
        except Exception as e:
            report.append(f"- **dnd5eapi:** Error ({str(e)})\n")

        
        report.append("\n")

    with open(REPORT_PATH, "w") as f:
        f.writelines(report)
    
    print(f"Probe complete. Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    probe_sources()

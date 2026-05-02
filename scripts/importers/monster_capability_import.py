#!/usr/bin/env python3
import json
import yaml
import os
import re
from typing import Dict, List, Any, Optional

# Paths
SAMPLE_DATA_DIR = "docs/reports/monster-source-samples"
OUTPUT_DIR = "monster_capabilities/samples"
LEGACY_DIR = "Monsters"

ABILITY_WORDS = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
    "str": "str",
    "dex": "dex",
    "con": "con",
    "int": "int",
    "wis": "wis",
    "cha": "cha",
}

CONDITION_WORDS = ("prone", "frightened", "grappled", "restrained", "poisoned")

def slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("'", "")
    text = re.sub(r"\s+", "-", text)
    return text or "action"

def canonical_action_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if text.endswith("s") and not text.endswith("ss"):
        text = text[:-1]
    return text

def compact_formula(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "")

def normalize_ability(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    return ABILITY_WORDS.get(raw)

def parse_save_metadata(desc: str) -> Dict[str, Any]:
    text = str(desc or "")
    match = re.search(
        r"dc\s+(\d+)\s+(strength|dexterity|constitution|intelligence|wisdom|charisma|str|dex|con|int|wis|cha)\s+saving throw",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return {}
    return {"save_dc": int(match.group(1)), "save_ability": normalize_ability(match.group(2))}

def parse_area_metadata(desc: str) -> Dict[str, Any]:
    text = str(desc or "")
    area: Dict[str, Any] = {}
    match = re.search(r"(\d+)\s*[- ]\s*foot\s+(cone|line|sphere|radius)", text, flags=re.IGNORECASE)
    if match:
        area["size"] = int(match.group(1))
        area["shape"] = match.group(2).lower()
    line_match = re.search(
        r"line\s+that\s+is\s+(\d+)\s+feet\s+long\s+and\s+(\d+)\s+feet\s+wide",
        text,
        flags=re.IGNORECASE,
    )
    if line_match:
        area["shape"] = "line"
        area["size"] = int(line_match.group(1))
        area["width"] = int(line_match.group(2))
    radius_match = re.search(r"(?:each creature|creatures?|target)\s+(?:of [^.]+? )?within\s+(\d+)\s+(?:ft\.?|feet)", text, flags=re.IGNORECASE)
    if radius_match and "shape" not in area:
        area["shape"] = "radius"
        area["size"] = int(radius_match.group(1))
    sphere_match = re.search(r"(\d+)\s*[- ]\s*foot-radius\s+sphere", text, flags=re.IGNORECASE)
    if sphere_match:
        area["shape"] = "sphere"
        area["size"] = int(sphere_match.group(1))
    return area

def parse_on_save(desc: str, success_type: Any = None, has_damage: bool = False) -> str:
    text = str(desc or "").lower()
    success = str(success_type or "").strip().lower()
    if "half as much damage" in text or "half damage" in text or success == "half":
        return "half"
    if "no damage" in text or success in {"none", "no_effect"}:
        return "none"
    if has_damage:
        return "manual"
    return "none"

def parse_range_metadata(desc: str) -> Dict[str, Any]:
    text = str(desc or "").lower()
    mechanics: Dict[str, Any] = {}
    reach_match = re.search(r"reach\s+(\d+)\s*ft", text)
    if reach_match:
        mechanics["reach"] = int(reach_match.group(1))
    range_match = re.search(r"range\s+(\d+)\s*/\s*(\d+)\s*ft", text)
    if range_match:
        mechanics["range"] = int(range_match.group(1))
        mechanics["long_range"] = int(range_match.group(2))
    return mechanics

def parse_duration_text(desc: str, condition: str) -> Optional[str]:
    text = str(desc or "")
    match = re.search(rf"{re.escape(condition)}(?:ed)?\s+for\s+([^.;]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def add_warning(cap: Dict[str, Any], code: str, detail: Optional[str] = None) -> None:
    warnings = cap.setdefault("warnings", [])
    entry: Dict[str, Any] = {"code": code}
    if detail:
        entry["detail"] = detail
    if entry not in warnings:
        warnings.append(entry)

def extract_riders(desc: str) -> List[Dict[str, Any]]:
    """Extract common condition riders from description text."""
    if not desc:
        return []
    
    effects = []
    desc_lower = desc.lower()
    save_meta = parse_save_metadata(desc)

    # 1. Prone
    if "knocked prone" in desc_lower or "is prone" in desc_lower:
        effect = {"kind": "condition", "condition": "prone", "text": "The target is knocked prone."}
        if save_meta:
            effect["trigger"] = "on_failed_save"
            effect["save_dc"] = save_meta.get("save_dc")
            effect["save_ability"] = save_meta.get("save_ability")
        else:
            effect["trigger"] = "on_hit"
        effects.append(effect)

    # 2. Frightened
    if "become frightened" in desc_lower or "is frightened" in desc_lower:
        effect = {"kind": "condition", "condition": "frightened", "text": "The target is frightened."}
        if save_meta:
            effect["trigger"] = "on_failed_save"
            effect["save_dc"] = save_meta.get("save_dc")
            effect["save_ability"] = save_meta.get("save_ability")
        else:
            effect["trigger"] = "on_failed_save"
        duration = parse_duration_text(desc, "frightened")
        if duration:
            effect["duration"] = duration
        if "repeat the saving throw" in desc_lower:
            effect["repeat_save"] = "end_of_turn"
        effects.append(effect)

    # 3. Poisoned
    if "is poisoned" in desc_lower or "become poisoned" in desc_lower:
        effect = {"kind": "condition", "condition": "poisoned", "text": "The target is poisoned."}
        if save_meta:
            effect["trigger"] = "on_failed_save"
            effect["save_dc"] = save_meta.get("save_dc")
            effect["save_ability"] = save_meta.get("save_ability")
        else:
            effect["trigger"] = "on_failed_save"
        duration = parse_duration_text(desc, "poisoned")
        if duration:
            effect["duration"] = duration
        effects.append(effect)

    # 4. Grappled / Restrained
    if "target is grappled" in desc_lower or "target is restrained" in desc_lower:
        cond = "restrained" if "restrained" in desc_lower else "grappled"
        effect = {"kind": "condition", "condition": cond, "text": f"The target is {cond}."}
        effect["trigger"] = "on_hit"
        m = re.search(r"escape dc (\d+)", desc_lower)
        if m:
            effect["escape_dc"] = int(m.group(1))
        effects.append(effect)

    return effects

def extract_manual_warnings(desc: str, cap: Dict[str, Any]) -> None:
    text = str(desc or "").lower()
    if not text:
        return
    if "has advantage" in text or "advantage on " in text or "can't benefit" in text:
        return
    if any(word in text for word in CONDITION_WORDS) and not cap.get("mechanics", {}).get("effects"):
        add_warning(cap, "ambiguous_condition_text", "Condition-like text was preserved for manual review.")
    if "if " in text and ("damage" in text or "attack" in text) and not cap.get("executable"):
        add_warning(cap, "manual_resolution_required", "Conditional trait/action remains display-only.")

def normalize_dnd_damage_entries(action: Dict[str, Any], on_save: Optional[str] = None) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for dmg in action.get("damage", []):
        if not isinstance(dmg, dict) or not dmg.get("damage_dice"):
            continue
        damage_type = dmg.get("damage_type", {}).get("index")
        if not damage_type:
            continue
        entry = {
            "formula": compact_formula(dmg.get("damage_dice")),
            "type": str(damage_type).strip().lower(),
        }
        if on_save:
            entry["on_save"] = on_save
        entries.append(entry)
    return entries

def apply_usage_metadata(cap: Dict[str, Any], usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    usage_type = str(usage.get("type") or "").strip().lower()
    if usage_type == "recharge on roll":
        cap["recharge"] = usage.get("min_value", 5)
    elif usage_type == "per day":
        try:
            max_uses = int(usage.get("times", 1) or 1)
        except Exception:
            max_uses = 1
        cap.setdefault("mechanics", {})["uses"] = {"max": max_uses, "per": "day"}

def normalize_o5e_action(action: Dict[str, Any], monster_slug: str) -> Dict[str, Any]:
    """Normalize an Open5e V2 action object."""
    cap = {
        "id": slugify(action.get("name", "action")),
        "name": action.get("name"),
        "type": "action",
        "executable": False,
        "desc": action.get("desc"),
        "action_type": "utility",
        "mechanics": {}
    }

    # ... (type and attack detection remains the same) ...
    # (re-pasting part of it to ensure context is correct for replace)
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
            
            damage_type = None
            if isinstance(atk.get("damage_type"), dict):
                damage_type = atk.get("damage_type", {}).get("key")
            if not damage_type:
                add_warning(cap, "source_damage_type_uncertain", "Open5e attack did not expose a reliable damage type.")
            else:
                cap["mechanics"]["damage"].append({
                    "formula": formula.lower(),
                    "type": str(damage_type).lower()
                })
        if atk.get("reach"):
            cap["mechanics"]["reach"] = int(atk.get("reach"))
        if atk.get("range"):
            cap["mechanics"]["range"] = int(atk.get("range"))
        if atk.get("long_range"):
            cap["mechanics"]["long_range"] = int(atk.get("long_range"))

    # Riders
    riders = extract_riders(cap["desc"])
    if riders:
        cap["mechanics"]["effects"] = riders

    # Multiattack detection
    # ...
    if "multiattack" in cap["name"].lower():
        cap["action_type"] = "composite"
        cap["executable"] = False 
        
        # Try to parse description
        desc = cap["desc"] or ""
        import re
        num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
        
        # Pattern 1: "one with its Bite and two with its Claws"
        matches = re.findall(r"(one|two|three|four|five|\d+)\s+(?:with its|with their)\s+([A-Za-z ]+?)(?=[,.]| and |$)", desc, re.IGNORECASE)
        if matches:
            cap["mechanics"]["composite"] = []
            for count_str, sub_name in matches:
                count = num_map.get(count_str.lower())
                if count is None:
                    try: count = int(count_str)
                    except: count = 1
                
                sub_name = sub_name.strip()
                
                cap["mechanics"]["composite"].append({
                    "action_id": slugify(sub_name),
                    "name": sub_name,
                    "count": count
                })
        
        # Pattern 2: "makes two scimitar attacks"
        if not cap["mechanics"].get("composite"):
            m = re.search(r"makes (one|two|three|four|five|\d+) ([A-Za-z ]+?) attacks", desc, re.IGNORECASE)
            if m:
                count_str, sub_name = m.groups()
                count = num_map.get(count_str.lower())
                if count is None:
                    try: count = int(count_str)
                    except: count = 1
                cap["mechanics"]["composite"] = [{
                    "action_id": slugify(sub_name),
                    "name": sub_name,
                    "count": count
                }]
    
    # Recharge detection
    if "recharge" in cap["name"].lower():
        cap["recharge"] = 5 # Default 5-6 if not specified

    extract_manual_warnings(cap.get("desc") or "", cap)

    return cap

def normalize_dnd5eapi_action(action: Dict[str, Any], monster_slug: str) -> Dict[str, Any]:
    """Normalize a dnd5eapi action object."""
    cap = {
        "id": slugify(action.get("name", "action")),
        "name": action.get("name"),
        "type": "action",
        "executable": False,
        "desc": action.get("desc"),
        "action_type": "utility",
        "mechanics": {}
    }

    # Check for spellcasting
    if "spellcasting" in action:
        s = action["spellcasting"]
        cap["action_type"] = "spellcasting"
        cap["mechanics"]["spellcasting"] = {
            "ability": s.get("ability", {}).get("index"),
            "save_dc": s.get("dc"),
            "attack_bonus": s.get("modifier"),
            "level": s.get("level"),
            "school": s.get("school"),
            "lists": []
        }
        
        # Group spells by frequency/resource
        # dnd5eapi spells are a flat list, we need to group them
        at_will = []
        daily = {} # uses -> list
        slots = {} # level -> list
        
        for spell in s.get("spells", []):
            name = spell.get("name")
            slug = slugify(name)
            usage = spell.get("usage")
            level = spell.get("level")
            
            if usage and usage.get("type") == "at will":
                at_will.append(slug)
            elif usage and usage.get("type") == "per day":
                uses = usage.get("times", 1)
                if uses not in daily: daily[uses] = []
                daily[uses].append(slug)
            elif level is not None:
                if level not in slots: slots[level] = []
                slots[level].append(slug)
        
        if at_will:
            cap["mechanics"]["spellcasting"]["lists"].append({
                "frequency": "at_will",
                "spells": at_will
            })
        for uses, spell_list in sorted(daily.items()):
            cap["mechanics"]["spellcasting"]["lists"].append({
                "frequency": "daily",
                "uses": uses,
                "spells": spell_list
            })
        slot_counts = s.get("slots", {})
        for level, spell_list in sorted(slots.items()):
            if level == 0:
                cap["mechanics"]["spellcasting"]["lists"].append({
                    "frequency": "at_will",
                    "level": 0,
                    "spells": spell_list
                })
            else:
                cap["mechanics"]["spellcasting"]["lists"].append({
                    "frequency": "slot",
                    "level": level,
                    "slots": int(slot_counts.get(str(level), 0)),
                    "spells": spell_list
                })

    apply_usage_metadata(cap, action.get("usage"))

    # Check for save ability
    dc = action.get("dc")
    if dc:
        cap["executable"] = True
        cap["action_type"] = "save_ability"
        damage_entries = action.get("damage", []) if isinstance(action.get("damage"), list) else []
        on_save = parse_on_save(action.get("desc", ""), dc.get("success_type"), bool(damage_entries))
        cap["mechanics"] = {
            "save_dc": dc.get("dc_value"),
            "save_ability": dc.get("dc_type", {}).get("index", "dex").lower(),
            "damage": [],
            "on_save": on_save,
        }
        area = parse_area_metadata(action.get("desc", ""))
        cap["mechanics"].update(area)

        # Damage for save
        cap["mechanics"]["damage"] = normalize_dnd_damage_entries(action, on_save=on_save)
        if on_save == "manual":
            add_warning(cap, "manual_save_outcome", "Save success behavior could not be confidently parsed.")

    # Check for attacks (if not already a save_ability)
    elif action.get("attack_bonus") is not None or action.get("damage"):
        cap["executable"] = True
        desc_lower = action.get("desc", "").lower()
        cap["action_type"] = "melee_attack" if "reach" in desc_lower else "ranged_attack"
        cap["mechanics"] = {
            "attack_bonus": action.get("attack_bonus"),
            "damage": []
        }
        cap["mechanics"]["damage"] = normalize_dnd_damage_entries(action)
        
        # Range/Reach extraction from desc if possible
        cap["mechanics"].update(parse_range_metadata(desc_lower))

    # Riders
    riders = extract_riders(cap["desc"])
    if riders:
        cap["mechanics"]["effects"] = riders

    # Multiattack detection
    if "multiattack" in cap["name"].lower():
        cap["action_type"] = "composite"
        cap["executable"] = False
        
        # dnd5eapi structured multiattack
        dnd_actions = action.get("actions", [])
        if dnd_actions:
            cap["mechanics"]["composite"] = []
            for sub in dnd_actions:
                sub_name = sub.get("action_name")
                if sub_name:
                    cap["mechanics"]["composite"].append({
                        "action_id": slugify(sub_name),
                        "name": sub_name,
                        "count": int(sub.get("count", 1))
                    })
        else:
            # Fallback to description parsing
            desc = cap["desc"] or ""
            import re
            # Simple patterns
            # 1. "makes two melee attacks"
            # 2. "makes three attacks: one with its bite and two with its claws"
            # 3. "makes two scimitar attacks"
            
            # Pattern 2: "one with its Bite and two with its Claws"
            # We look for "one with its ([A-Za-z ]+)" or "([0-9]|two|three) with its ([A-Za-z ]+)"
            num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            matches = re.findall(r"(one|two|three|four|five|\d+)\s+(?:with its|with their)\s+([A-Za-z ]+?)(?=[,.]| and |$)", desc, re.IGNORECASE)
            if matches:
                cap["mechanics"]["composite"] = []
                for count_str, sub_name in matches:
                    count = num_map.get(count_str.lower())
                    if count is None:
                        try: count = int(count_str)
                        except: count = 1
                    
                    sub_name = sub_name.strip()
                    
                    cap["mechanics"]["composite"].append({
                        "action_id": slugify(sub_name),
                        "name": sub_name,
                        "count": count
                    })
            
            # Pattern 3: "makes two scimitar attacks"
            if not cap["mechanics"].get("composite"):
                m = re.search(r"makes (one|two|three|four|five|\d+) ([A-Za-z ]+?) attacks", desc, re.IGNORECASE)
                if m:
                    count_str, sub_name = m.groups()
                    count = num_map.get(count_str.lower())
                    if count is None:
                        try: count = int(count_str)
                        except: count = 1
                    cap["mechanics"]["composite"] = [{
                        "action_id": slugify(sub_name),
                        "name": sub_name,
                        "count": count
                    }]

    extract_manual_warnings(cap.get("desc") or "", cap)

    return cap

def validate_composite_children(norm: Dict[str, Any]) -> None:
    caps = norm.get("capabilities", []) if isinstance(norm.get("capabilities"), list) else []
    by_key: Dict[str, Dict[str, Any]] = {}
    for cap in caps:
        if not isinstance(cap, dict):
            continue
        by_key[canonical_action_key(cap.get("id"))] = cap
        by_key[canonical_action_key(cap.get("name"))] = cap

    for cap in caps:
        if not isinstance(cap, dict) or cap.get("action_type") != "composite":
            continue
        mechanics = cap.get("mechanics") if isinstance(cap.get("mechanics"), dict) else {}
        composite = mechanics.get("composite") if isinstance(mechanics.get("composite"), list) else []
        for child in composite:
            if not isinstance(child, dict):
                continue
            match = by_key.get(canonical_action_key(child.get("action_id"))) or by_key.get(canonical_action_key(child.get("name")))
            if match:
                child["action_id"] = match.get("id")
                child["name"] = match.get("name")
                child["matched"] = True
                child["executable"] = bool(match.get("executable"))
            else:
                child["matched"] = False
                child["executable"] = False
                add_warning(cap, "unmatched_multiattack_child", f"Could not match multiattack child {child.get('name') or child.get('action_id')}.")

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
            # Try to normalize traits if they have actions/usage/spellcasting
            cap = normalize_dnd5eapi_action(trait, target_slug)
            cap["type"] = "trait"
            norm["capabilities"].append(cap)
    else:
        # Fallback to O5E normalization
        for action in data.get("actions", []):
            norm["capabilities"].append(normalize_o5e_action(action, target_slug))
        for trait in data.get("traits", []):
            norm["capabilities"].append({
                "id": slugify(trait.get("name", "trait")),
                "name": trait.get("name"),
                "type": "trait",
                "executable": False,
                "desc": trait.get("desc"),
                "action_type": "utility",
                "mechanics": {},
                "warnings": [{"code": "manual_resolution_required", "detail": "Open5e trait fallback is display-only."}],
            })

    validate_composite_children(norm)

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

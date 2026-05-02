import os
import yaml
import glob
from typing import Dict, List, Any, Optional

class MonsterCapabilityService:
    """Service for loading and matching normalized monster capability overlays."""

    def __init__(self, root_dir: str = "monster_capabilities", spells_dir: str = "Spells"):
        self.root_dir = root_dir
        self.spells_dir = spells_dir
        self.capabilities_by_slug: Dict[str, Dict[str, Any]] = {}
        self.spells_by_slug: Dict[str, Dict[str, Any]] = {}
        self.load_all_capabilities()
        self.load_all_spells()

    def load_all_capabilities(self):
        """Load all normalized capability YAMLs from the root directory."""
        self.capabilities_by_slug = {}
        # Pattern to match all YAMLs in subdirectories (like samples/)
        pattern = os.path.join(self.root_dir, "**", "*.yaml")
        files = glob.glob(pattern, recursive=True)

        for f in sorted(files):
            try:
                with open(f, "r", encoding="utf-8") as stream:
                    data = yaml.safe_load(stream)
                    if data and isinstance(data, dict) and "slug" in data:
                        # Basic normalization
                        if "capabilities" not in data:
                            data["capabilities"] = []
                        # Store by lowercase slug
                        self.capabilities_by_slug[data["slug"].lower()] = data
            except Exception as e:
                # For this pass, we just print/log and continue
                print(f"Error loading monster capability {f}: {e}")

    def load_all_spells(self):
        """Load all spell YAMLs from the spells directory."""
        self.spells_by_slug = {}
        if not os.path.exists(self.spells_dir):
            return
            
        pattern = os.path.join(self.spells_dir, "**", "*.yaml")
        files = glob.glob(pattern, recursive=True)
        
        for f in sorted(files):
            try:
                with open(f, "r", encoding="utf-8") as stream:
                    data = yaml.safe_load(stream)
                    if data and isinstance(data, dict):
                        slug = os.path.splitext(os.path.basename(f))[0].lower()
                        self.spells_by_slug[slug] = data
            except Exception as e:
                print(f"Error loading spell {f}: {e}")

    def get_spell_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieve spell definition by slug."""
        return self.spells_by_slug.get(slug.lower())

    def get_capability_by_slug(self, slug: Optional[str]) -> Optional[Dict[str, Any]]:
        """Retrieve capability overlay by slug."""
        if not slug:
            return None
        return self.capabilities_by_slug.get(slug.lower())

    def match_capabilities_for_combatant(self, combatant: Any) -> Optional[Dict[str, Any]]:
        """Match an active combatant to a capability overlay.

        Handles both raw combatant objects and dictionaries.
        """
        slug = None

        # 1. Try explicit monster_slug
        if isinstance(combatant, dict):
            slug = combatant.get("monster_slug")
        else:
            slug = getattr(combatant, "monster_slug", None)

        # 2. Try to derive from monster_spec
        if not slug:
            spec = None
            if isinstance(combatant, dict):
                spec = combatant.get("monster_spec")
            else:
                spec = getattr(combatant, "monster_spec", None)

            if spec:
                # MonsterSpec has filename and name
                filename = getattr(spec, "filename", "") if not isinstance(spec, dict) else spec.get("filename")
                if filename:
                    slug = os.path.splitext(os.path.basename(filename))[0]
                else:
                    name = getattr(spec, "name", "") if not isinstance(spec, dict) else spec.get("name")
                    if name:
                        slug = str(name).lower().replace(" ", "-")

        # 3. Fallback to combatant name
        if not slug:
            name = combatant.get("name", "") if isinstance(combatant, dict) else getattr(combatant, "name", "")
            if name:
                # Remove numeric suffixes (e.g. "Goblin 1" -> "goblin")
                base_name = str(name).rstrip(" 0123456789")
                slug = base_name.lower().strip().replace(" ", "-")

        return self.get_capability_by_slug(slug)

    def summarize_capabilities_for_ui(self, combatant_id: int, combatant: Any) -> Dict[str, Any]:
        """Produce a UI-friendly summary of capabilities for a specific combatant."""
        data = self.match_capabilities_for_combatant(combatant)

        name = ""
        if isinstance(combatant, dict):
            name = combatant.get("name", "Unknown")
        else:
            name = getattr(combatant, "name", "Unknown")

        if not data:
            return {
                "matched": False,
                "combatant_id": combatant_id,
                "name": name,
                "groups": {}
            }

        # Group by type per schema
        groups = {
            "actions": [],
            "bonus_actions": [],
            "reactions": [],
            "legendary_actions": [],
            "traits": [],
            "lair_actions": [],
            "special": []
        }

        for cap in data.get("capabilities", []):
            ctype = cap.get("type", "special")
            action_type = cap.get("action_type")
            mechanics = cap.get("mechanics", {})

            # Include effects
            effects = mechanics.get("effects")
            if effects:
                cap["effects"] = effects

            # Resolve spellcasting
            if action_type == "spellcasting" and "spellcasting" in mechanics:
                s = mechanics["spellcasting"]
                resolved_lists = []
                for lst in s.get("lists", []):
                    resolved_spells = []
                    for slug in lst.get("spells", []):
                        spell_data = self.get_spell_by_slug(slug)
                        resolved = {
                            "slug": slug,
                            "name": spell_data.get("name", slug.replace("-", " ").title()) if spell_data else slug.replace("-", " ").title(),
                            "matched": spell_data is not None,
                            "level": spell_data.get("level") if spell_data else None,
                            "casting_time": spell_data.get("casting_time") if spell_data else None,
                        }
                        # Add basic mechanics if matched
                        if spell_data:
                            m = spell_data.get("mechanics", {})
                            resolved["automation"] = m.get("automation", "manual")
                            # Try to extract damage/save info from local spell
                            if "sequence" in m:
                                for seq in m["sequence"]:
                                    if "check" in seq and seq["check"].get("kind") == "saving_throw":
                                        resolved["save_ability"] = seq["check"].get("ability")
                                    if "outcomes" in seq:
                                        # Very basic extraction for UI
                                        resolved["has_damage"] = True
                        resolved_spells.append(resolved)
                    
                    resolved_lst = dict(lst)
                    resolved_lst["resolved_spells"] = resolved_spells
                    resolved_lists.append(resolved_lst)
                cap["mechanics"]["resolved_lists"] = resolved_lists

            # Resolve composite children
            if action_type == "composite" and "composite" in mechanics:
                resolved_children = []
                for child in cap["mechanics"]["composite"]:
                    child_id = child.get("action_id")
                    # Find matching capability in the same monster
                    matched_child = next((c for c in data.get("capabilities", []) if c.get("id") == child_id), None)

                    resolved = {
                        "action_id": child_id,
                        "name": child.get("name"),
                        "count": child.get("count", 1),
                        "matched": matched_child is not None,
                        "executable": matched_child.get("executable", False) if matched_child else False
                    }
                    resolved_children.append(resolved)
                # Store in mechanics so it's serialized to UI
                cap["mechanics"]["resolved_composite"] = resolved_children

            # Include recharge if present
            recharge = cap.get("recharge")
            if recharge:
                cap["recharge_rule"] = f"{recharge}-6" if isinstance(recharge, int) else str(recharge)

            # Include generic uses if present
            uses = mechanics.get("uses")
            if uses:
                cap["uses_max"] = uses.get("max")
                cap["uses_per"] = uses.get("per")

            # Map type to plural groups
            key = ctype + "s" if not ctype.endswith("s") else ctype
            if key in groups:
                groups[key].append(cap)
            else:
                groups["special"].append(cap)

        return {
            "matched": True,
            "combatant_id": combatant_id,
            "slug": data.get("slug"),
            "name": name,
            "monster_name": data.get("name"),
            "source": data.get("source"),
            "license": data.get("license"),
            "groups": groups
        }

import os
import yaml
import glob
import re
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

    @staticmethod
    def _area_metadata_for_capability(cap: Dict[str, Any]) -> Dict[str, Any]:
        mechanics = cap.get("mechanics", {}) if isinstance(cap.get("mechanics"), dict) else {}
        desc = str(cap.get("desc") or "")
        area: Dict[str, Any] = {}
        shape = str(mechanics.get("shape") or "").strip().lower()
        size = mechanics.get("size")
        if not shape:
            match = re.search(r"(\d+)\s*-\s*foot\s+(cone|line|sphere|radius)", desc, flags=re.IGNORECASE)
            if match:
                size = int(match.group(1))
                shape = match.group(2).lower()
        if not shape:
            match = re.search(r"within\s+(\d+)\s*ft\.?", desc, flags=re.IGNORECASE)
            if match:
                size = int(match.group(1))
                shape = "radius"
        if shape:
            area["shape"] = shape
        if size is not None:
            try:
                area["size"] = int(size)
            except Exception:
                area["size"] = size
        # Weapon range/long_range describe single-target reach; they are not AoE
        # and must not populate area metadata. Only true AoE shape/size makes
        # this an area capability.
        return area

    @classmethod
    def _target_mode_for_capability(cls, cap: Dict[str, Any]) -> str:
        mechanics = cap.get("mechanics", {}) if isinstance(cap.get("mechanics"), dict) else {}
        desc = str(cap.get("desc") or "").lower()
        action_type = str(cap.get("action_type") or "")
        if "self" in str(mechanics.get("target") or "").lower():
            return "self"
        area = cls._area_metadata_for_capability(cap)
        if area and (area.get("shape") or area.get("size")):
            return "area_manual"
        if action_type == "save_ability" and (
            "each creature" in desc or "creatures of" in desc or "creature within" in desc or "creatures within" in desc
        ):
            return "multiple"
        if mechanics.get("targets") not in (None, "", 1, "1"):
            return "multiple"
        return "single"

    @classmethod
    def _outcome_options_for_capability(cls, cap: Dict[str, Any]) -> List[Dict[str, Any]]:
        mechanics = cap.get("mechanics", {}) if isinstance(cap.get("mechanics"), dict) else {}
        action_type = str(cap.get("action_type") or "")
        options: List[Dict[str, Any]] = []
        damage = mechanics.get("damage") if isinstance(mechanics.get("damage"), list) else []
        effects = mechanics.get("effects") if isinstance(mechanics.get("effects"), list) else []
        if action_type == "save_ability":
            if damage:
                options.append({"outcome": "fail", "label": "Failed save damage", "damage": "full"})
                options.append({"outcome": "success", "label": "Successful save damage", "damage": "half_or_none"})
            if effects:
                options.append(
                    {
                        "outcome": "fail",
                        "label": "Failed save effects",
                        "effects": [
                            {
                                "kind": eff.get("kind"),
                                "condition": eff.get("condition"),
                                "trigger": eff.get("trigger"),
                                "text": eff.get("text"),
                            }
                            for eff in effects
                            if isinstance(eff, dict)
                        ],
                    }
                )
            options.append({"outcome": "no_effect", "label": "No effect"})
            options.append({"outcome": "manual", "label": "Manual notes"})
        elif effects:
            options.append(
                {
                    "outcome": "manual",
                    "label": "Manual effect",
                    "effects": [
                        {
                            "kind": eff.get("kind"),
                            "condition": eff.get("condition"),
                            "trigger": eff.get("trigger"),
                            "text": eff.get("text"),
                        }
                        for eff in effects
                        if isinstance(eff, dict)
                    ],
                }
            )
        return options

    def summarize_capabilities_for_ui(self, combatant_id: int, combatant: Any, resource_state: Dict[str, Any] = None, pending_modifiers: List[Dict[str, Any]] = None) -> Dict[str, Any]:
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
            cap_id = cap.get("id")
            action_type = cap.get("action_type")
            mechanics = cap.get("mechanics", {}) if isinstance(cap.get("mechanics"), dict) else {}

            # Include effects
            effects = mechanics.get("effects")
            if effects:
                cap["effects"] = effects

            cap["target_mode"] = self._target_mode_for_capability(cap)
            area = self._area_metadata_for_capability(cap)
            if area:
                cap["area"] = area

            # Expose weapon range/reach as flat fields so target-advisory UIs
            # can read them without inferring from area metadata. These are
            # never area metadata; they are single-target distance limits.
            try:
                if mechanics.get("range") is not None:
                    cap["range_ft"] = int(mechanics.get("range"))
            except Exception:
                pass
            try:
                if mechanics.get("long_range") is not None:
                    cap["long_range_ft"] = int(mechanics.get("long_range"))
            except Exception:
                pass
            try:
                if mechanics.get("reach") is not None:
                    cap["reach_ft"] = int(mechanics.get("reach"))
            except Exception:
                pass
            outcome_options = self._outcome_options_for_capability(cap)
            if outcome_options:
                cap["outcome_options"] = outcome_options
            cap["multi_target_capable"] = cap["target_mode"] in {"multiple", "area_manual"} or bool(area)

            # Generate mechanics_summary for UI
            summary_parts = []

            # Add ammo info if present in resource_state
            if resource_state:
                ammo_current = resource_state.get(f"{combatant_id}:ammo:{cap_id}:current")
                ammo_max = resource_state.get(f"{combatant_id}:ammo:{cap_id}:max")
                if ammo_current is not None:
                    summary_parts.append(f"Loaded: {ammo_current}/{ammo_max}")
                    # Add structured ammo info for prominent display in detail panels
                    cap["ammo"] = {
                        "current": ammo_current,
                        "max": ammo_max
                    }

                # Reserve mags
                ammo_type = mechanics.get("ammo_type")
                if ammo_type:
                    reserve_mags = resource_state.get(f"{combatant_id}:ammo:{ammo_type}:reserve_mags")
                    if reserve_mags is not None:
                        summary_parts.append(f"Reserves: {reserve_mags} mags")
                        if "ammo" not in cap: cap["ammo"] = {}
                        cap["ammo"]["reserve_mags"] = reserve_mags
                        cap["ammo"]["type"] = ammo_type

            if action_type in ["melee_attack", "ranged_attack"]:
                bonus = mechanics.get("attack_bonus")
                if bonus is not None:
                    summary_parts.append(f"+{bonus} to hit")

                dmg = mechanics.get("damage")
                if dmg and isinstance(dmg, list):
                    dmg_parts = []
                    for d in dmg:
                        if isinstance(d, dict) and d.get("formula"):
                            dmg_parts.append(f"{d['formula']} {d.get('type', '')}")
                    if dmg_parts:
                        summary_parts.append("/".join(dmg_parts))

                reach = mechanics.get("reach")
                if reach:
                    summary_parts.append(f"reach {reach}ft")

                rng = mechanics.get("range")
                if rng:
                    long_rng = mechanics.get("long_range")
                    if long_rng:
                        summary_parts.append(f"range {rng}/{long_rng}ft")
                    else:
                        summary_parts.append(f"range {rng}ft")

            elif action_type == "save_ability":
                ability = mechanics.get("ability", "STR").upper()
                dc = mechanics.get("dc")
                if dc:
                    summary_parts.append(f"DC {dc} {ability}")

                # Show damage for save abilities (e.g. area effects)
                dmg = mechanics.get("damage")
                if dmg and isinstance(dmg, list):
                    dmg_parts = []
                    for d in dmg:
                        if isinstance(d, dict) and d.get("formula"):
                            dmg_parts.append(f"{d['formula']} {d.get('type', '')}")
                    if dmg_parts:
                        summary_parts.append("/".join(dmg_parts))

            elif action_type == "modifier":
                mod = mechanics.get("modifier", {})

                # Status for modifiers
                is_armed = False
                if pending_modifiers:
                    is_armed = any(m.get("capability_id") == cap_id for m in pending_modifiers)

                is_used = False
                if resource_state:
                    is_used = bool(resource_state.get(f"{combatant_id}:mod_used:{cap_id}"))

                if is_armed:
                    summary_parts.append("ARMED")
                elif is_used:
                    summary_parts.append("USED")
                else:
                    summary_parts.append("Available")

                ammo_cost = mod.get("ammo_cost")
                if ammo_cost:
                    summary_parts.append(f"{ammo_cost} ammo")
                    cap["ammo_cost"] = ammo_cost
                db = mod.get("damage_bonus", {})
                if db.get("mode") == "extra_weapon_die":
                    count = db.get("count", 1)
                    summary_parts.append(f"+{count} weapon die" if count == 1 else f"+{count} weapon dice")
                if mod.get("jam_risk") == "natural_1":
                    summary_parts.append("Jam risk (1)")
                if mod.get("limit") == "once_per_turn":
                    summary_parts.append("1/turn")

            elif action_type == "firearm_reload":
                summary_parts.append("Reload Firearms")

            elif action_type == "utility":
                # Show conditions or healing for utility actions
                effects = mechanics.get("effects")
                if effects and isinstance(effects, list):
                    for eff in effects:
                        if isinstance(eff, dict) and eff.get("condition"):
                            summary_parts.append(f"Effect: {eff['condition']}")

                uses = mechanics.get("uses")
                if uses and isinstance(uses, dict):
                    max_uses = uses.get("max")
                    per = uses.get("per")
                    if max_uses:
                        summary_parts.append(f"{max_uses}/{per or 'encounter'}")

            # Include riders for any action type if present
            riders = mechanics.get("riders")
            if riders and isinstance(riders, list):
                for r in riders:
                    if isinstance(r, dict) and r.get("name"):
                        summary_parts.append(f"Rider: {r['name']}")

            # Add reload/ammo note if present in description or mechanics
            desc = cap.get("desc", "")
            if "reload" in desc.lower() or "ammo" in desc.lower() or "magazine" in desc.lower():
                # Extract simple note if possible
                match = re.search(r"(reload|ammo|magazine)\s*(\d+)", desc, re.I)
                if match:
                    summary_parts.append(match.group(0))
                elif "reload" in desc.lower():
                    summary_parts.append("Reload required")

            if not summary_parts and desc:
                # Fallback to a truncated description if no structured mechanics summary
                summary_parts.append(desc[:60] + ("..." if len(desc) > 60 else ""))

            cap["mechanics_summary"] = " • ".join(summary_parts)

            # Generate manual_instructions if non-executable or special
            instructions = []
            if cap.get("executable") is False:
                warning = cap.get("warning")
                if warning:
                    instructions.append(warning)
                else:
                    instructions.append("Manual adjudication required.")

            if "grapple" in desc.lower():
                instructions.append("Apply Grappled condition manually in /dm if hit.")
            if "prone" in desc.lower():
                instructions.append("Apply Prone condition manually in /dm if hit.")
            if "ammo" in desc.lower() or "magazine" in desc.lower():
                # Only show if not already tracked by backend
                has_backend_ammo = False
                if resource_state:
                    ammo_current = resource_state.get(f"{combatant_id}:ammo:{cap_id}:current")
                    if ammo_current is not None:
                        has_backend_ammo = True

                if not has_backend_ammo:
                    instructions.append("Track ammunition manually.")

            if instructions:
                cap["manual_instructions"] = " ".join(instructions)

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
                comp_data = mechanics["composite"]

                # Default values for sequence
                sequence_kind = mechanics.get("sequence_kind", "fixed_children")
                choose_n = mechanics.get("choose_n")
                children = []

                if isinstance(comp_data, list):
                    children = comp_data
                elif isinstance(comp_data, dict):
                    children = comp_data.get("children", [])
                    sequence_kind = comp_data.get("sequence_kind", sequence_kind)
                    choose_n = comp_data.get("choose_n", choose_n)

                # Ensure sequence_kind is one of the supported values or default to fixed_children
                if sequence_kind not in ["fixed_children", "choose_n"]:
                    # Normalize unknown to fixed_children for now
                    sequence_kind = "fixed_children"

                # Expose sequence metadata at top level of mechanics for easier UI access
                cap["mechanics"]["sequence_kind"] = sequence_kind
                if choose_n is not None:
                    cap["mechanics"]["choose_n"] = choose_n

                resolved_children = []
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    child_id = child.get("action_id")
                    # Find matching capability in the same monster
                    matched_child = next((c for c in data.get("capabilities", []) if c.get("id") == child_id), None)

                    resolved = {
                        "action_id": child_id,
                        "name": child.get("name") or (matched_child.get("name") if matched_child else child_id),
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

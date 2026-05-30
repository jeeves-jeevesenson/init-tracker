#!/usr/bin/env python3
"""Deterministic quality gate for normalized monster capability overlays."""

import argparse
import glob
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

import yaml


DEFAULT_OVERLAY_ROOT = "monster_capabilities"
DEFAULT_REPORT_PATH = "docs/reports/monster-capability-quality.md"
DEFAULT_SPELLS_DIR = "Spells"

SUPPORTED_CONDITIONS = {
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
    "braced",
    "suppressed",
}

ATTACK_ACTION_TYPES = {"melee_attack", "ranged_attack"}
AREA_HINT_RE = re.compile(
    r"\b(cone|line|sphere|radius)\b|within\s+\d+\s*(?:ft\.?|feet)|\d+\s*[- ]\s*foot",
    re.IGNORECASE,
)
DURATION_HINT_RE = re.compile(
    r"\b(?:for|until)\s+(?:\d+\s+)?(?:round|minute|hour|day|turn|the end|it escapes)",
    re.IGNORECASE,
)
MANUAL_HINT_RE = re.compile(
    r"\b(if|must|saving throw|damage|attack|action|bonus action|reaction|regain|regains)\b",
    re.IGNORECASE,
)
VAGUE_VALUES = {"", "unknown", "todo", "tbd", "none"}


@dataclass(order=True)
class Finding:
    severity: str
    code: str
    message: str
    capability_id: str = ""


@dataclass
class OverlayResult:
    path: str
    slug: str = "unknown"
    name: str = "Unknown"
    capability_count: int = 0
    errors: List[Finding] = field(default_factory=list)
    warnings: List[Finding] = field(default_factory=list)

    def add_error(self, code: str, message: str, capability_id: str = "") -> None:
        self.errors.append(Finding("error", code, message, capability_id))

    def add_warning(self, code: str, message: str, capability_id: str = "") -> None:
        self.warnings.append(Finding("warning", code, message, capability_id))


def _slugify(value: Any) -> str:
    text = str(value or "").strip().lower().replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _relative_path(path: str) -> str:
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _has_vague_or_missing(value: Any) -> bool:
    return str(value or "").strip().lower() in VAGUE_VALUES


def _cap_label(cap: Dict[str, Any], index: int) -> str:
    return str(cap.get("id") or cap.get("name") or f"capability[{index}]")


def iter_overlay_paths(root: str = DEFAULT_OVERLAY_ROOT) -> List[str]:
    return sorted(glob.glob(os.path.join(root, "**", "*.yaml"), recursive=True))


def load_local_spell_slugs(spells_dir: str = DEFAULT_SPELLS_DIR) -> Set[str]:
    if not os.path.isdir(spells_dir):
        return set()
    slugs: Set[str] = set()
    for path in sorted(glob.glob(os.path.join(spells_dir, "**", "*.yaml"), recursive=True)):
        slugs.add(os.path.splitext(os.path.basename(path))[0].lower())
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            if isinstance(data, dict):
                slug = data.get("slug") or data.get("id")
                if slug:
                    slugs.add(str(slug).strip().lower())
        except Exception:
            continue
    return slugs


def _validate_damage_entries(
    result: OverlayResult,
    cap: Dict[str, Any],
    cap_id: str,
    damage_entries: List[Any],
    *,
    executable: bool,
) -> None:
    for idx, entry in enumerate(damage_entries):
        if not isinstance(entry, dict):
            result.add_error("damage_entry_not_object", f"Damage entry {idx} is not an object.", cap_id)
            continue
        if executable and not str(entry.get("formula") or "").strip():
            result.add_error("executable_damage_missing_formula", f"Damage entry {idx} is missing formula.", cap_id)
        damage_type = str(entry.get("type") or "").strip().lower()
        if not damage_type or damage_type == "unspecified":
            result.add_warning("damage_type_missing", f"Damage entry {idx} has no specific damage type.", cap_id)


def _validate_recharge(result: OverlayResult, cap: Dict[str, Any], cap_id: str) -> None:
    if "recharge" in cap:
        recharge = cap.get("recharge")
        try:
            threshold = int(recharge)
        except (TypeError, ValueError):
            text = str(recharge or "").strip().lower()
            if text not in {"short_rest", "long_rest", "day", "daily", "encounter"}:
                result.add_error("recharge_unparseable", f"Recharge value {recharge!r} is not understood.", cap_id)
        else:
            if threshold < 2 or threshold > 6:
                result.add_error("recharge_out_of_range", f"Recharge threshold {threshold} must be between 2 and 6.", cap_id)

    uses = _as_dict(_as_dict(cap.get("mechanics")).get("uses"))
    if uses:
        try:
            max_uses = int(uses.get("max"))
        except (TypeError, ValueError):
            result.add_error("uses_max_unparseable", "Limited-use resource has nonnumeric max uses.", cap_id)
        else:
            if max_uses <= 0:
                result.add_error("uses_max_invalid", "Limited-use resource max uses must be positive.", cap_id)


def _validate_effects(result: OverlayResult, cap: Dict[str, Any], cap_id: str) -> None:
    mechanics = _as_dict(cap.get("mechanics"))
    desc = str(cap.get("desc") or "")
    effects = _as_list(mechanics.get("effects"))
    for idx, effect in enumerate(effects):
        if not isinstance(effect, dict):
            result.add_error("effect_not_object", f"Effect entry {idx} is not an object.", cap_id)
            continue
        kind = str(effect.get("kind") or "").strip().lower()
        condition = str(effect.get("condition") or "").strip().lower()
        if kind == "condition":
            if not condition:
                result.add_warning("assisted_effect_missing_condition", f"Condition effect {idx} is missing condition.", cap_id)
            elif condition not in SUPPORTED_CONDITIONS:
                result.add_error(
                    "unsupported_condition",
                    f"Condition effect {idx} uses unsupported condition {condition!r}.",
                    cap_id,
                )
            if not effect.get("duration") and DURATION_HINT_RE.search(desc):
                result.add_warning(
                    "effect_duration_missing",
                    f"Condition effect {idx} has no duration metadata but description appears time-bound.",
                    cap_id,
                )


def _validate_composite(result: OverlayResult, cap: Dict[str, Any], cap_id: str, local_ids: Set[str], local_names: Set[str]) -> None:
    mechanics = _as_dict(cap.get("mechanics"))
    children = _as_list(mechanics.get("composite"))
    for idx, child in enumerate(children):
        if not isinstance(child, dict):
            result.add_error("composite_child_not_object", f"Composite child {idx} is not an object.", cap_id)
            continue
        action_id = str(child.get("action_id") or "").strip()
        name = str(child.get("name") or "").strip()
        if not action_id and not name:
            result.add_error("composite_child_missing_identifier", f"Composite child {idx} has no action_id or name.", cap_id)
            continue
        action_key = _slugify(action_id)
        name_key = _slugify(name)
        matched_by_reference = bool(action_key and action_key in local_ids) or bool(name_key and name_key in local_names)
        if child.get("matched") is False or (not matched_by_reference and child.get("matched") is not True):
            label = action_id or name
            result.add_warning("composite_child_unmatched", f"Composite child {label!r} does not match a local capability.", cap_id)


def _validate_spellcasting(
    result: OverlayResult,
    cap: Dict[str, Any],
    cap_id: str,
    local_spell_slugs: Optional[Set[str]],
) -> None:
    if not local_spell_slugs:
        return
    spellcasting = _as_dict(_as_dict(cap.get("mechanics")).get("spellcasting"))
    for group_idx, group in enumerate(_as_list(spellcasting.get("lists"))):
        if not isinstance(group, dict):
            continue
        for slug in _as_list(group.get("spells")):
            spell_slug = str(slug or "").strip().lower()
            if spell_slug and spell_slug not in local_spell_slugs:
                result.add_warning(
                    "spell_unmatched_local_yaml",
                    f"Spellcasting group {group_idx} references local-unmatched spell {spell_slug!r}.",
                    cap_id,
                )


def validate_overlay_data(
    data: Any,
    path: str,
    *,
    local_spell_slugs: Optional[Set[str]] = None,
) -> OverlayResult:
    result = OverlayResult(path=_relative_path(path))
    if not isinstance(data, dict):
        result.add_error("overlay_not_object", "Overlay YAML must be a top-level object.")
        return result

    name = data.get("name")
    slug = data.get("slug")
    if not str(name or "").strip():
        result.add_error("missing_top_level_name", "Overlay is missing top-level name.")
    else:
        result.name = str(name).strip()
    if not str(slug or "").strip():
        result.add_error("missing_top_level_slug", "Overlay is missing top-level slug.")
    else:
        result.slug = str(slug).strip()

    basename_slug = os.path.splitext(os.path.basename(path))[0]
    if slug and basename_slug and basename_slug != str(slug).strip():
        result.add_warning("path_slug_mismatch", f"File slug {basename_slug!r} does not match overlay slug {slug!r}.")

    if _has_vague_or_missing(data.get("source")):
        result.add_warning("source_missing_or_vague", "Top-level source is missing or vague.")
    if _has_vague_or_missing(data.get("license")):
        result.add_warning("license_missing_or_vague", "Top-level license is missing or vague.")

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list):
        result.add_error("missing_capabilities_list", "Overlay is missing top-level capabilities list.")
        return result
    result.capability_count = len(capabilities)

    seen_ids: Set[str] = set()
    local_ids: Set[str] = set()
    local_names: Set[str] = set()
    for idx, cap in enumerate(capabilities):
        if not isinstance(cap, dict):
            continue
        cap_id = str(cap.get("id") or "").strip()
        if cap_id:
            key = cap_id.lower()
            if key in seen_ids:
                result.add_error("duplicate_capability_id", f"Duplicate capability id {cap_id!r}.", cap_id)
            seen_ids.add(key)
            local_ids.add(_slugify(cap_id))
        name_key = _slugify(cap.get("name"))
        if name_key:
            local_names.add(name_key)

    for idx, cap in enumerate(capabilities):
        if not isinstance(cap, dict):
            result.add_error("capability_not_object", f"Capability entry {idx} is not an object.")
            continue
        cap_id = _cap_label(cap, idx)
        action_type = str(cap.get("action_type") or "").strip()
        executable = bool(cap.get("executable"))
        mechanics = _as_dict(cap.get("mechanics"))
        desc = str(cap.get("desc") or "").strip()
        warnings = _as_list(cap.get("warnings"))

        if not str(cap.get("id") or "").strip():
            result.add_error("missing_capability_id", f"Capability entry {idx} is missing id.", cap_id)
        if not desc:
            result.add_warning("capability_desc_missing", "Capability has no desc/display text.", cap_id)

        damage_entries = _as_list(mechanics.get("damage"))
        _validate_damage_entries(result, cap, cap_id, damage_entries, executable=executable)

        if executable and action_type in ATTACK_ACTION_TYPES:
            if mechanics.get("attack_bonus") is None:
                result.add_error("executable_attack_missing_attack_bonus", "Executable attack is missing mechanics.attack_bonus.", cap_id)
            if not damage_entries:
                result.add_error("executable_attack_missing_damage", "Executable attack is missing mechanics.damage entries.", cap_id)

        if action_type == "save_ability":
            if mechanics.get("save_dc") is None:
                result.add_error("save_ability_missing_dc", "Save ability is missing mechanics.save_dc.", cap_id)
            if not str(mechanics.get("save_ability") or "").strip():
                result.add_error("save_ability_missing_ability", "Save ability is missing mechanics.save_ability.", cap_id)
            if damage_entries:
                mechanics_on_save = str(mechanics.get("on_save") or "").strip()
                entry_on_save = [str(entry.get("on_save") or "").strip() for entry in damage_entries if isinstance(entry, dict)]
                if not mechanics_on_save and not all(entry_on_save):
                    result.add_error("save_ability_damage_missing_on_save", "Save ability damage entries need explicit on_save metadata.", cap_id)
            if desc and AREA_HINT_RE.search(desc) and not str(mechanics.get("shape") or "").strip():
                result.add_warning("save_area_metadata_missing", "Save ability description mentions area/range but mechanics.shape is missing.", cap_id)

        if action_type == "composite":
            _validate_composite(result, cap, cap_id, local_ids, local_names)

        if action_type == "spellcasting":
            _validate_spellcasting(result, cap, cap_id, local_spell_slugs)

        _validate_effects(result, cap, cap_id)
        _validate_recharge(result, cap, cap_id)

        if executable:
            for warning in warnings:
                if isinstance(warning, dict) and "uncertain" in str(warning.get("code") or "").lower():
                    result.add_warning("executable_uncertain_warning", "Executable capability carries an uncertainty warning.", cap_id)

        if not executable and action_type not in {"spellcasting", "composite"} and not warnings and desc and MANUAL_HINT_RE.search(desc):
            result.add_warning("manual_action_without_warning", "Display-only/manual capability has no warning or reason.", cap_id)

    return result


def validate_overlay_file(path: str, *, local_spell_slugs: Optional[Set[str]] = None) -> OverlayResult:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except Exception as exc:
        result = OverlayResult(path=_relative_path(path))
        result.add_error("yaml_unreadable", f"YAML could not be read or parsed: {exc}")
        return result
    return validate_overlay_data(data, path, local_spell_slugs=local_spell_slugs)


def validate_overlay_paths(paths: Iterable[str], *, local_spell_slugs: Optional[Set[str]] = None) -> List[OverlayResult]:
    results = [validate_overlay_file(path, local_spell_slugs=local_spell_slugs) for path in sorted(paths)]
    slug_to_results: Dict[str, List[OverlayResult]] = {}
    for result in results:
        if result.slug and result.slug != "unknown":
            slug_to_results.setdefault(result.slug, []).append(result)
    for slug, dupes in sorted(slug_to_results.items()):
        if len(dupes) > 1:
            files = ", ".join(_relative_path(item.path) for item in dupes)
            for item in dupes:
                item.add_warning("duplicate_monster_slug", f"Duplicate monster slug {slug!r} appears in: {files}.")
    return results


def scan_overlays(root: str = DEFAULT_OVERLAY_ROOT, *, spells_dir: str = DEFAULT_SPELLS_DIR) -> List[OverlayResult]:
    return validate_overlay_paths(iter_overlay_paths(root), local_spell_slugs=load_local_spell_slugs(spells_dir))


def count_findings(results: List[OverlayResult]) -> Dict[str, int]:
    return {
        "overlays": len(results),
        "capabilities": sum(item.capability_count for item in results),
        "errors": sum(len(item.errors) for item in results),
        "warnings": sum(len(item.warnings) for item in results),
    }


HARD_ERROR_RULES = [
    "YAML unreadable or malformed.",
    "Missing top-level name, slug, or capabilities list.",
    "Duplicate capability ids within one overlay.",
    "Executable attack missing attack_bonus or damage entries.",
    "Executable damage entry missing formula.",
    "Save ability missing save_dc or save_ability.",
    "Save ability damage missing explicit on_save metadata.",
    "Composite child missing both action_id and name.",
    "Applyable condition effect uses an unsupported condition.",
    "Recharge or limited-use metadata is impossible to interpret.",
]

WARNING_RULES = [
    "Save ability text mentions area/range but mechanics.shape is missing.",
    "Damage type missing or unspecified.",
    "Executable action carries importer uncertainty warning.",
    "Composite child is unmatched to a local capability.",
    "Spellcasting group references a local-unmatched spell slug.",
    "Condition rider appears time-bound but has no duration metadata.",
    "Condition effect is missing condition metadata.",
    "Capability has no desc/display text.",
    "Display-only/manual capability has no warning or reason.",
    "Source/license fields are missing or vague.",
    "Duplicate monster slug across overlay files.",
    "Overlay file path slug does not match top-level slug.",
]


def render_markdown_report(results: List[OverlayResult]) -> str:
    totals = count_findings(results)
    lines = [
        "# Monster Capability Quality Report",
        "",
        "## Summary",
        f"- Total overlays scanned: {totals['overlays']}",
        f"- Total capabilities scanned: {totals['capabilities']}",
        f"- Hard errors: {totals['errors']}",
        f"- Warnings: {totals['warnings']}",
        "",
        "## Per-Monster Summary",
        "",
        "| Slug | File | Capabilities | Errors | Warnings |",
        "|------|------|--------------|--------|----------|",
    ]
    for result in sorted(results, key=lambda item: (item.slug, item.path)):
        lines.append(
            f"| {result.slug} | `{_relative_path(result.path)}` | {result.capability_count} | {len(result.errors)} | {len(result.warnings)} |"
        )

    lines.extend(["", "## Detailed Findings", ""])
    findings_found = False
    for result in sorted(results, key=lambda item: (item.slug, item.path)):
        findings = sorted(result.errors + result.warnings)
        if not findings:
            continue
        findings_found = True
        lines.append(f"### {result.slug}")
        lines.append("")
        lines.append(f"- File: `{_relative_path(result.path)}`")
        for finding in findings:
            cap_suffix = f" `{finding.capability_id}`" if finding.capability_id else ""
            lines.append(f"- {finding.severity.upper()} `{finding.code}`{cap_suffix}: {finding.message}")
        lines.append("")
    if not findings_found:
        lines.append("No findings.")
        lines.append("")

    lines.extend(["## Rules Checked", "", "### Hard Errors", ""])
    lines.extend(f"- {rule}" for rule in HARD_ERROR_RULES)
    lines.extend(["", "### Warnings", ""])
    lines.extend(f"- {rule}" for rule in WARNING_RULES)
    lines.append("")
    return "\n".join(lines)


def write_report(report_path: str, content: str) -> None:
    directory = os.path.dirname(report_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(content)


def run_quality_gate(
    *,
    root: str = DEFAULT_OVERLAY_ROOT,
    report_path: str = DEFAULT_REPORT_PATH,
    spells_dir: str = DEFAULT_SPELLS_DIR,
    strict: bool = False,
) -> Dict[str, Any]:
    results = scan_overlays(root, spells_dir=spells_dir)
    report = render_markdown_report(results)
    write_report(report_path, report)
    totals = count_findings(results)
    exit_code = 1 if totals["errors"] or (strict and totals["warnings"]) else 0
    return {"results": results, "totals": totals, "report_path": report_path, "exit_code": exit_code}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate normalized monster capability overlays.")
    parser.add_argument("--root", default=DEFAULT_OVERLAY_ROOT, help="Overlay root to scan.")
    parser.add_argument("--report", default=DEFAULT_REPORT_PATH, help="Markdown report path to write.")
    parser.add_argument("--spells-dir", default=DEFAULT_SPELLS_DIR, help="Local spell YAML directory for spellcasting references.")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as hard errors.")
    args = parser.parse_args(argv)

    outcome = run_quality_gate(root=args.root, report_path=args.report, spells_dir=args.spells_dir, strict=args.strict)
    totals = outcome["totals"]
    print("Monster capability quality gate")
    print(
        f"Overlays: {totals['overlays']}  "
        f"Capabilities: {totals['capabilities']}  "
        f"Errors: {totals['errors']}  "
        f"Warnings: {totals['warnings']}"
    )
    print(f"Report: {outcome['report_path']}")
    if args.strict and totals["warnings"]:
        print("Strict mode: warnings are treated as failures.")
    return int(outcome["exit_code"])


if __name__ == "__main__":
    sys.exit(main())

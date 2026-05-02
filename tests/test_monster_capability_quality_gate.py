import os
import tempfile
import unittest

import yaml

from scripts.audit.monster_capability_quality_gate import (
    render_markdown_report,
    run_quality_gate,
    validate_overlay_data,
    validate_overlay_paths,
)


def _base_overlay(capabilities):
    return {
        "name": "Test Monster",
        "slug": "test-monster",
        "source": "unit-test",
        "license": "CC-BY-4.0",
        "capabilities": capabilities,
    }


def _finding_codes(result, severity):
    findings = result.errors if severity == "error" else result.warnings
    return {finding.code for finding in findings}


class TestMonsterCapabilityQualityGate(unittest.TestCase):
    def test_valid_sample_overlays_have_no_hard_errors(self):
        paths = [
            os.path.join("monster_capabilities", "samples", name)
            for name in sorted(os.listdir(os.path.join("monster_capabilities", "samples")))
            if name.endswith(".yaml")
        ]
        results = validate_overlay_paths(paths)
        errors = [finding for result in results for finding in result.errors]
        self.assertEqual(errors, [])

    def test_executable_attack_missing_damage_is_hard_error(self):
        result = validate_overlay_data(
            _base_overlay(
                [
                    {
                        "id": "claw",
                        "name": "Claw",
                        "type": "action",
                        "executable": True,
                        "desc": "Melee Weapon Attack: +4 to hit.",
                        "action_type": "melee_attack",
                        "mechanics": {"attack_bonus": 4, "damage": []},
                    }
                ]
            ),
            "test-monster.yaml",
        )
        self.assertIn("executable_attack_missing_damage", _finding_codes(result, "error"))

    def test_save_ability_missing_dc_is_hard_error(self):
        result = validate_overlay_data(
            _base_overlay(
                [
                    {
                        "id": "breath",
                        "name": "Breath",
                        "type": "action",
                        "executable": True,
                        "desc": "Each creature in a 15-foot cone must make a Dexterity saving throw.",
                        "action_type": "save_ability",
                        "mechanics": {"save_ability": "dex", "shape": "cone", "damage": []},
                    }
                ]
            ),
            "test-monster.yaml",
        )
        self.assertIn("save_ability_missing_dc", _finding_codes(result, "error"))

    def test_composite_child_missing_identifier_is_hard_error(self):
        result = validate_overlay_data(
            _base_overlay(
                [
                    {
                        "id": "multiattack",
                        "name": "Multiattack",
                        "type": "action",
                        "executable": False,
                        "desc": "The monster makes two attacks.",
                        "action_type": "composite",
                        "mechanics": {"composite": [{"count": 2}]},
                    }
                ]
            ),
            "test-monster.yaml",
        )
        self.assertIn("composite_child_missing_identifier", _finding_codes(result, "error"))

    def test_unsupported_condition_is_hard_error(self):
        result = validate_overlay_data(
            _base_overlay(
                [
                    {
                        "id": "stare",
                        "name": "Stare",
                        "type": "action",
                        "executable": False,
                        "desc": "The target is doomed.",
                        "action_type": "utility",
                        "mechanics": {"effects": [{"kind": "condition", "condition": "doomed", "trigger": "manual"}]},
                    }
                ]
            ),
            "test-monster.yaml",
        )
        self.assertIn("unsupported_condition", _finding_codes(result, "error"))

    def test_unspecified_damage_type_is_warning_not_error(self):
        result = validate_overlay_data(
            _base_overlay(
                [
                    {
                        "id": "claw",
                        "name": "Claw",
                        "type": "action",
                        "executable": True,
                        "desc": "Melee Weapon Attack: +4 to hit. Hit: 4 damage.",
                        "action_type": "melee_attack",
                        "mechanics": {"attack_bonus": 4, "damage": [{"formula": "1d6+1", "type": "unspecified"}]},
                    }
                ]
            ),
            "test-monster.yaml",
        )
        self.assertNotIn("damage_type_missing", _finding_codes(result, "error"))
        self.assertIn("damage_type_missing", _finding_codes(result, "warning"))

    def test_duplicate_capability_id_is_hard_error(self):
        result = validate_overlay_data(
            _base_overlay(
                [
                    {"id": "bite", "name": "Bite", "desc": "Bite.", "action_type": "utility", "mechanics": {}},
                    {"id": "bite", "name": "Bite Again", "desc": "Bite.", "action_type": "utility", "mechanics": {}},
                ]
            ),
            "test-monster.yaml",
        )
        self.assertIn("duplicate_capability_id", _finding_codes(result, "error"))

    def test_quality_report_can_be_generated_in_temp_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = os.path.join(tmpdir, "monster_capabilities", "samples")
            os.makedirs(root)
            path = os.path.join(root, "test-monster.yaml")
            with open(path, "w", encoding="utf-8") as handle:
                yaml.safe_dump(
                    _base_overlay(
                        [
                            {
                                "id": "claw",
                                "name": "Claw",
                                "type": "action",
                                "executable": True,
                                "desc": "Melee Weapon Attack: +4 to hit. Hit: 4 (1d6+1) slashing damage.",
                                "action_type": "melee_attack",
                                "mechanics": {
                                    "attack_bonus": 4,
                                    "damage": [{"formula": "1d6+1", "type": "slashing"}],
                                },
                            }
                        ]
                    ),
                    handle,
                    sort_keys=False,
                )
            report_path = os.path.join(tmpdir, "monster-capability-quality.md")
            outcome = run_quality_gate(root=os.path.join(tmpdir, "monster_capabilities"), report_path=report_path)
            self.assertEqual(outcome["totals"]["errors"], 0)
            self.assertTrue(os.path.exists(report_path))
            with open(report_path, "r", encoding="utf-8") as handle:
                report = handle.read()
            self.assertIn("# Monster Capability Quality Report", report)

    def test_markdown_report_contains_rule_summary(self):
        result = validate_overlay_data(_base_overlay([]), "test-monster.yaml")
        report = render_markdown_report([result])
        self.assertIn("## Rules Checked", report)
        self.assertIn("Total overlays scanned: 1", report)


if __name__ == "__main__":
    unittest.main()

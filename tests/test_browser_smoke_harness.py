import unittest
import subprocess
import os
import json
import importlib.util
import shutil
import sys
from pathlib import Path

# Ensure the scripts directory is in the path if needed, 
# but we are calling it via subprocess which is safer for CLI tests.

class TestBrowserSmokeHarness(unittest.TestCase):
    def setUp(self):
        self.test_root = Path("logs/test-browser-smoke")
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_help(self):
        """Verify --help works and shows usage."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: browser-smoke-harness.py", result.stdout)
        self.assertIn("--list-scenarios", result.stdout)
        self.assertIn("--scenario", result.stdout)

    def test_list_scenarios(self):
        """Verify --list-scenarios shows the Scorcher scenario."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--list-scenarios"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("scorcher-ignite-ground", result.stdout)
        self.assertIn("Black and Tan VDA Scorcher Ignite Ground pilot", result.stdout)

    def test_list_exploration_scenario(self):
        """Verify --list-scenarios shows the exploration scenario."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--list-scenarios"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("black-tan-combat-exploration", result.stdout)
        self.assertIn("All Players vs All Black and Tans combat exploration", result.stdout)

    def test_multi_round_cli_args(self):
        """Verify the multi-round CLI arguments are accepted."""
        # Just check if --help shows them
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--max-rounds", result.stdout)
        self.assertIn("--max-turns", result.stdout)
        self.assertIn("--slow-mo-ms", result.stdout)

    def test_scorcher_scenario_attempt_artifacts(self):
        """Verify the Scorcher scenario attempt creates artifacts even on failure."""
        # This will fail because no server is running, but it should create artifacts
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", 
             "--scenario", "scorcher-ignite-ground", 
             "--artifact-root", str(self.test_root),
             "--base-url", "http://localhost:9999"], # Non-existent server
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)

        # Verify artifact directory was created
        self.assertTrue(self.test_root.exists())
        # The structure is now: artifact-root / scenario-id / timestamp
        scenario_dir = self.test_root / "scorcher-ignite-ground"
        self.assertTrue(scenario_dir.exists())

        runs = list(scenario_dir.iterdir())
        self.assertEqual(len(runs), 1)

        run_dir = runs[0]
        summary_path = run_dir / "summary.json"
        self.assertTrue(summary_path.exists())

        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
            self.assertEqual(summary["scenario"], "scorcher-ignite-ground")
            self.assertEqual(summary["status"], "fail")
            self.assertIn("dm", summary["roles"])
            self.assertIn("artifacts", summary)
            # Screenshots might be empty if it failed before browser launch or during run
            self.assertIn("screenshots", summary["artifacts"])

    def test_unknown_scenario(self):
        """Verify unknown scenario IDs fail with a useful message."""
        result = subprocess.run(
            [sys.executable, "scripts/validation/browser-smoke-harness.py", "--scenario", "non-existent"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error: Unknown scenario 'non-existent'", result.stderr)

if __name__ == "__main__":
    unittest.main()


_HARNESS_MODULE = None


def _load_browser_smoke_harness():
    global _HARNESS_MODULE
    if _HARNESS_MODULE is None:
        path = Path("scripts/validation/browser-smoke-harness.py")
        spec = importlib.util.spec_from_file_location("browser_smoke_harness_g1c", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _HARNESS_MODULE = module
    return _HARNESS_MODULE


def _complete_three_surface_verification_response(harness):
    players = []
    enemies = []
    player_map = {}
    enemy_map = {}
    for index, (player_id, name) in enumerate(harness.THREE_SURFACE_PLAYER_IDENTITIES, start=1):
        cid = 100 + index
        player_map[player_id] = cid
        players.append({
            "player_id": player_id,
            "name": name,
            "cid": cid,
            "position": {"col": index, "row": index + 1},
        })
    for index, (enemy_slug, name) in enumerate(harness.THREE_SURFACE_ENEMY_IDENTITIES, start=1):
        cid = 200 + index
        enemy_map[enemy_slug] = cid
        enemies.append({
            "enemy_slug": enemy_slug,
            "name": name,
            "cid": cid,
            "position": {"col": 20 + index, "row": index + 2},
        })
    return {
        "ok": True,
        "schema_version": harness.THREE_SURFACE_SCHEMA_VERSION,
        "operation": "verify-ui-workflow",
        "reset_version": harness.THREE_SURFACE_RESET_VERSION,
        "precondition_digest": harness.THREE_SURFACE_PRECONDITION_DIGEST,
        "players": players,
        "enemies": enemies,
        "player_cid_map": player_map,
        "enemy_cid_map": enemy_map,
        "player_count": 10,
        "enemy_count": 9,
        "combatant_count": 19,
        "in_combat": True,
        "mutated": False,
    }


def test_three_surface_plan_uses_verified_selectors_and_ordered_steps():
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()

    assert plan["scenario_id"] == "black-tan-three-surface-workflow"
    assert [surface["path"] for surface in plan["surfaces"]] == ["/dm", "/dmcontrol", "/"]
    assert [step["order"] for step in plan["steps"]] == list(range(1, len(plan["steps"]) + 1))
    assert plan["steps"][0]["step_id"] == "pin-contract-expectation"
    assert plan["steps"][0]["browser_interaction"] is False

    enemy_steps = [step for step in plan["steps"] if step["step_id"].startswith("add-enemy-")]
    assert [step["value"] for step in enemy_steps] == [
        slug for slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]
    assert all(step["count"] == 1 and step["ally"] is False for step in enemy_steps)
    assert all(step["selector"] == "#monsterSlugSelect" for step in enemy_steps)
    assert all(step["submit_selector"] == "#addMonsterBtn" for step in enemy_steps)

    step_ids = [step["step_id"] for step in plan["steps"]]
    assert "select-all-roster-players" in step_ids
    assert "add-all-roster-players" in step_ids
    assert "start-combat" in step_ids
    assert "validate-complete-runtime-mappings" in step_ids
    assert "assert-dm-visible-state" in step_ids
    assert "assert-dmcontrol-visible-state" in step_ids
    assert "assert-player-visible-state" in step_ids
    assert sum(step_id.startswith("claim-player-") for step_id in step_ids) == 10
    assert sum(step_id.startswith("player-attack-") for step_id in step_ids) == 5
    assert sum(step_id.startswith("player-spell-") for step_id in step_ids) == 5
    assert sum(step_id.startswith("enemy-action-") for step_id in step_ids) == 9
    assert any(step.get("apply_selector") == "#modalApplyBtn" for step in plan["steps"])
    assert any(step.get("smoke_api") == "handleCombatControl()" for step in plan["steps"])


def test_three_surface_plan_requires_versioned_fixture_contract():
    harness = _load_browser_smoke_harness()
    request = harness.three_surface_fixture_request("verify-ui-workflow")

    assert request["schema_version"] == "a7-ui-reset-contract/v1"
    assert request["reset_version"] == "blank-combat/v1"
    assert request["expected_precondition_digest"] == (
        "sha256:67668370769a7a7f81c820550d4a10033bde8e297b2da1d05d55819cade90873"
    )
    assert request["players"] == [
        {"player_id": player_id, "name": name}
        for player_id, name in harness.THREE_SURFACE_PLAYER_IDENTITIES
    ]
    assert request["enemies"] == [
        {"enemy_slug": enemy_slug, "name": name}
        for enemy_slug, name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]

    response = _complete_three_surface_verification_response(harness)
    result = harness.validate_three_surface_fixture_contract(response, "verify-ui-workflow")
    assert result["ok"] is True
    assert result["terminal"] is False

    wrong_version = dict(response)
    wrong_version["schema_version"] = "a7-ui-reset-contract/v0"
    result = harness.validate_three_surface_fixture_contract(wrong_version, "verify-ui-workflow")
    assert result["ok"] is False
    assert result["reason"] == "fixture-precondition-mismatch"


def test_three_surface_contract_mismatch_is_terminal_without_retry():
    harness = _load_browser_smoke_harness()
    pinned_digest = harness.THREE_SURFACE_PRECONDITION_DIGEST
    response = {
        "ok": False,
        "error": "precondition_mismatch",
        "mismatch_details": [
            {"field": "schema_version", "expected": "a7-ui-reset-contract/v1", "actual": "v0"}
        ],
        "actual_precondition_digest": "sha256:" + "f" * 64,
        "mutated": False,
    }

    result = harness.classify_three_surface_contract_response(response, "reset-ui-workflow")

    assert result["terminal"] is True
    assert result["terminal_classification"] == "fail"
    assert result["reason"] == "fixture-precondition-mismatch"
    assert result["retry"] is False
    assert result["rewrite_expectation"] is False
    assert result["later_workflow_steps"] == 0
    assert len(result["failure_detail"]) <= 512
    assert harness.THREE_SURFACE_PRECONDITION_DIGEST == pinned_digest


def test_three_surface_evidence_schema_records_required_artifacts_and_timings(tmp_path):
    harness = _load_browser_smoke_harness()
    evidence = harness.build_three_surface_evidence(
        run_id="run-a7-g1c-001",
        terminal_classification="fail",
        step_timings=[
            {"order": 1, "step_id": "pin-contract-expectation", "duration_ms": 1},
            {"order": 2, "step_id": "reset-ui-workflow", "duration_ms": 2},
        ],
        screenshots=[str(tmp_path / "dm.png"), str(tmp_path / "player.png")],
        browser_trace=str(tmp_path / "browser-trace.zip"),
        server_log=str(tmp_path / "server.log"),
        debug_trace=str(tmp_path / "debug-trace.jsonl"),
        fixture_evidence={"reset": {"mutated": True}, "verify": {"mutated": False}},
        port_ownership={"port": 8787, "verified": True, "pid": 1234},
        cleanup_disposition={"status": "owned-process-cleaned", "cleaned": True},
        failure_detail="x" * 800,
        role_traces={"dm": str(tmp_path / "dm-trace.zip")},
    )

    assert evidence["evidence_schema_version"] == "a7-three-surface-evidence/v1"
    assert evidence["scenario_id"] == "black-tan-three-surface-workflow"
    assert evidence["run_id"] == "run-a7-g1c-001"
    assert evidence["terminal_classification"] == "fail"
    assert [entry["order"] for entry in evidence["ordered_step_timings"]] == [1, 2]
    assert set(evidence["artifacts"]) == {
        "screenshots", "browser_trace", "server_log", "debug_trace", "role_traces"
    }
    assert evidence["fixture_evidence"]["verify"]["mutated"] is False
    assert evidence["port_ownership"]["verified"] is True
    assert evidence["cleanup_disposition"]["cleaned"] is True
    assert len(evidence["failure_detail"]) == 512


def test_three_surface_cleanup_refuses_unverified_process_ownership():
    harness = _load_browser_smoke_harness()

    class FakeProcess:
        pid = 4321

        def __init__(self):
            self.calls = []

        def poll(self):
            self.calls.append("poll")
            return None

        def terminate(self):
            self.calls.append("terminate")

        def wait(self, timeout):
            self.calls.append(("wait", timeout))

        def kill(self):
            self.calls.append("kill")

    process = FakeProcess()
    disposition = harness.cleanup_owned_process(
        process,
        {"verified": False, "pid": process.pid, "source": "unknown"},
    )

    assert disposition == {
        "status": "refused-unverified-process-ownership",
        "cleaned": False,
        "pid": 4321,
    }
    assert process.calls == []

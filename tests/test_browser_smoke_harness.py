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


def test_three_surface_roster_setup_precedes_encounter_tab():
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    step_ids = [step["step_id"] for step in plan["steps"]]
    open_toolbox_index = step_ids.index("open-toolbox")
    expected_setup_order = [
        "open-toolbox",
        "select-all-roster-players",
        "add-all-roster-players",
        "open-encounter",
    ]
    expected_enemy_order = [
        f"add-enemy-{enemy_slug}"
        for enemy_slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]

    assert step_ids[open_toolbox_index:open_toolbox_index + 4] == expected_setup_order
    assert step_ids[open_toolbox_index + 4:open_toolbox_index + 13] == expected_enemy_order


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


class _FakeTracing:
    def __init__(self):
        self.start_calls = []
        self.stop_calls = []

    def start(self, **kwargs):
        self.start_calls.append(kwargs)

    def stop(self, **kwargs):
        self.stop_calls.append(kwargs)


class _FakeContext:
    def __init__(self):
        self.tracing = _FakeTracing()


class _FakePage:
    def __init__(self):
        self.context = _FakeContext()


class _FakeEnemyOptionPage(_FakePage):
    def __init__(self, option_values):
        super().__init__()
        self.option_values = list(option_values)
        self.select_calls = []
        self.fill_calls = []
        self.check_calls = []
        self.uncheck_calls = []
        self.click_calls = []

    def wait_for_selector(self, _selector, **_kwargs):
        return None

    def eval_on_selector_all(self, selector, _expression):
        assert selector == "#monsterSlugSelect option"
        return list(self.option_values)

    def select_option(self, selector, value):
        self.select_calls.append((selector, value))

    def fill(self, selector, value):
        self.fill_calls.append((selector, value))

    def check(self, selector):
        self.check_calls.append(selector)

    def uncheck(self, selector):
        self.uncheck_calls.append(selector)

    def click(self, selector):
        self.click_calls.append(selector)


class _FakeCollector:
    def __init__(self, root):
        self.root = root
        self.timestamp = "20260716_120000"
        self.screenshots = []

    def get_path(self, filename):
        return self.root / filename

    def capture_screenshot(self, _page, name):
        path = self.root / f"{name}.png"
        self.screenshots.append(str(path))


def _fake_three_surface_pages(harness):
    pages = {
        "dm": _FakePage(),
        "dmcontrol": _FakePage(),
    }
    pages.update({
        f"player:{player_id}": _FakePage()
        for player_id, _name in harness.THREE_SURFACE_PLAYER_IDENTITIES
    })
    return pages


def _three_surface_enemy_steps(plan):
    return [
        step for step in plan["steps"]
        if step["step_id"].startswith("add-enemy-")
    ]


def _execute_enemy_option_step(harness, plan, step, page, state):
    harness._execute_three_surface_step(
        step,
        plan,
        "http://example.invalid",
        {"dm": page},
        None,
        {},
        state,
    )


def _enemy_option_failure(harness, option_values):
    plan = harness.build_three_surface_workflow_plan()
    step = _three_surface_enemy_steps(plan)[0]
    page = _FakeEnemyOptionPage(option_values)
    state = {"enemy_options_validated": False}
    try:
        _execute_enemy_option_step(harness, plan, step, page, state)
    except harness.ThreeSurfaceTerminalFailure as exc:
        return exc, page, state
    raise AssertionError("enemy-option validation unexpectedly passed")


def test_three_surface_scenario_executes_registered_executor(monkeypatch, tmp_path):
    harness = _load_browser_smoke_harness()
    assert harness.THREE_SURFACE_EXECUTORS[harness.THREE_SURFACE_SCENARIO_ID] is (
        harness.execute_three_surface_workflow
    )
    calls = []

    def fake_registered_executor(plan, base_url, pages, collector, config):
        calls.append((plan, base_url, pages, collector, config))
        return True, {"executor": "fake-registered-executor"}

    monkeypatch.setitem(
        harness.THREE_SURFACE_EXECUTORS,
        harness.THREE_SURFACE_SCENARIO_ID,
        fake_registered_executor,
    )
    scenario = harness.BlackTanThreeSurfaceWorkflowScenario()
    collector = _FakeCollector(tmp_path)

    result = scenario.run("http://example.invalid", {}, collector, {})

    assert result == (True, {"executor": "fake-registered-executor"})
    assert len(calls) == 1
    assert calls[0][0] is scenario.plan
    assert calls[0][1] == "http://example.invalid"


def test_three_surface_executor_runs_ordered_plan_once(monkeypatch, tmp_path):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    pages = _fake_three_surface_pages(harness)
    collector = _FakeCollector(tmp_path)
    executed = []

    def fake_step(step, plan_arg, base_url, pages_arg, collector_arg, config, state):
        assert plan_arg is plan
        assert base_url == "http://example.invalid"
        assert pages_arg is pages
        assert collector_arg is collector
        executed.append((step["order"], step["step_id"]))

    monkeypatch.setattr(harness, "_execute_three_surface_step", fake_step)

    success, evidence = harness.execute_three_surface_workflow(
        plan,
        "http://example.invalid",
        pages,
        collector,
        {
            "port_ownership": {"port": 8787, "verified": True, "pid": 1234},
            "cleanup_disposition": {"status": "owned-process-cleaned", "cleaned": True},
        },
    )

    expected = [(step["order"], step["step_id"]) for step in plan["steps"]]
    assert success is True
    assert executed == expected
    assert len(executed) == len(set(executed))
    assert evidence["executed_step_count"] == len(plan["steps"])
    assert [timing["order"] for timing in evidence["ordered_step_timings"]] == [
        step["order"] for step in plan["steps"]
    ]
    assert all(timing["duration_ms"] >= 0 for timing in evidence["ordered_step_timings"])
    assert all(timing["status"] == "pass" for timing in evidence["ordered_step_timings"])
    assert evidence["artifacts"]["browser_trace"].endswith("browser-trace.zip")
    assert set(evidence["artifacts"]["role_traces"]) == set(pages)
    assert all(page.context.tracing.start_calls for page in pages.values())
    assert all(page.context.tracing.stop_calls for page in pages.values())


def test_three_surface_corrected_setup_steps_execute_once(monkeypatch, tmp_path):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    pages = _fake_three_surface_pages(harness)
    collector = _FakeCollector(tmp_path)
    executed = []

    def fake_step(step, *_args):
        executed.append(step["step_id"])

    monkeypatch.setattr(harness, "_execute_three_surface_step", fake_step)

    success, _evidence = harness.execute_three_surface_workflow(
        plan,
        "http://example.invalid",
        pages,
        collector,
        {},
    )

    corrected_setup_steps = [
        "open-toolbox",
        "select-all-roster-players",
        "add-all-roster-players",
        "open-encounter",
        *(
            f"add-enemy-{enemy_slug}"
            for enemy_slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
        ),
    ]
    assert success is True
    assert [step_id for step_id in executed if step_id in corrected_setup_steps] == (
        corrected_setup_steps
    )
    assert all(executed.count(step_id) == 1 for step_id in corrected_setup_steps)


def test_three_surface_enemy_options_accept_reordered_complete_set():
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    enemy_steps = _three_surface_enemy_steps(plan)
    expected_slugs = [
        slug for slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]
    page = _FakeEnemyOptionPage(list(reversed(expected_slugs)))
    state = {"enemy_options_validated": False}

    for step in enemy_steps:
        _execute_enemy_option_step(harness, plan, step, page, state)

    assert state["enemy_options_validated"] is True
    assert page.select_calls == [
        ("#monsterSlugSelect", slug) for slug in expected_slugs
    ]
    assert page.fill_calls == [("#monsterCount", "1")] * len(enemy_steps)
    assert page.check_calls == []
    assert page.uncheck_calls == ["#monsterAlly"] * len(enemy_steps)
    assert page.click_calls == ["#addMonsterBtn"] * len(enemy_steps)


def test_three_surface_enemy_options_reject_missing_slug():
    harness = _load_browser_smoke_harness()
    expected_slugs = [
        slug for slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]

    failure, page, state = _enemy_option_failure(harness, expected_slugs[1:])

    assert failure.reason == "visible-state-inconsistency"
    assert failure.detail["missing_enemy_slugs"] == [expected_slugs[0]]
    assert failure.detail["extra_enemy_slugs"] == []
    assert failure.detail["duplicate_enemy_slugs"] == []
    assert state["enemy_options_validated"] is False
    assert page.select_calls == []
    assert page.click_calls == []


def test_three_surface_enemy_options_reject_extra_slug():
    harness = _load_browser_smoke_harness()
    expected_slugs = [
        slug for slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]
    extra_slug = "black-and-tan-unexpected"

    failure, page, state = _enemy_option_failure(
        harness,
        [*expected_slugs, extra_slug],
    )

    assert failure.reason == "visible-state-inconsistency"
    assert failure.detail["missing_enemy_slugs"] == []
    assert failure.detail["extra_enemy_slugs"] == [extra_slug]
    assert failure.detail["duplicate_enemy_slugs"] == []
    assert state["enemy_options_validated"] is False
    assert page.select_calls == []
    assert page.click_calls == []


def test_three_surface_enemy_options_reject_duplicate_slug():
    harness = _load_browser_smoke_harness()
    expected_slugs = [
        slug for slug, _name in harness.THREE_SURFACE_ENEMY_IDENTITIES
    ]
    duplicate_slug = expected_slugs[0]

    failure, page, state = _enemy_option_failure(
        harness,
        [*expected_slugs, duplicate_slug],
    )

    assert failure.reason == "visible-state-inconsistency"
    assert failure.detail["missing_enemy_slugs"] == []
    assert failure.detail["extra_enemy_slugs"] == []
    assert failure.detail["duplicate_enemy_slugs"] == [duplicate_slug]
    assert state["enemy_options_validated"] is False
    assert page.select_calls == []
    assert page.click_calls == []


def test_three_surface_executor_failure_records_terminal_evidence(monkeypatch, tmp_path):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    pages = _fake_three_surface_pages(harness)
    collector = _FakeCollector(tmp_path)
    failing_step = "open-toolbox"

    def fake_step(step, *_args):
        if step["step_id"] == failing_step:
            raise harness.ThreeSurfaceTerminalFailure(
                "selector-failure",
                {"selector": "#openToolboxBtn", "detail": "x" * 800},
            )

    monkeypatch.setattr(harness, "_execute_three_surface_step", fake_step)

    success, evidence = harness.execute_three_surface_workflow(
        plan,
        "http://example.invalid",
        pages,
        collector,
        {
            "server_log": str(tmp_path / "server.log"),
            "debug_trace": str(tmp_path / "debug.jsonl"),
            "port_ownership": {"port": 8787, "verified": True, "pid": 1234},
            "cleanup_disposition": {"status": "owned-process-cleaned", "cleaned": True},
        },
    )

    assert success is False
    assert evidence["terminal_classification"] == "fail"
    assert evidence["failure_step_id"] == failing_step
    assert evidence["executed_step_count"] == 5
    assert evidence["ordered_step_timings"][-1]["status"] == "fail"
    assert "selector-failure" in evidence["failure_detail"]
    assert evidence["failure_detail"].startswith("selector-failure:")
    assert len(evidence["failure_detail"]) <= 512
    assert evidence["artifacts"]["screenshots"]
    assert evidence["artifacts"]["browser_trace"].endswith("browser-trace.zip")
    assert set(evidence["artifacts"]["role_traces"]) == set(pages)
    assert evidence["artifacts"]["server_log"].endswith("server.log")
    assert evidence["artifacts"]["debug_trace"].endswith("debug.jsonl")
    assert evidence["port_ownership"]["verified"] is True
    assert evidence["cleanup_disposition"]["status"] == "owned-process-cleaned"


def test_three_surface_executor_never_retries_after_failure(monkeypatch, tmp_path):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    pages = _fake_three_surface_pages(harness)
    collector = _FakeCollector(tmp_path)
    executed = []

    def fake_step(step, *_args):
        executed.append(step["step_id"])
        if step["step_id"] == "reset-ui-workflow":
            raise harness.ThreeSurfaceTerminalFailure(
                "fixture-precondition-mismatch",
                "reset contract mismatch",
            )

    monkeypatch.setattr(harness, "_execute_three_surface_step", fake_step)

    success, evidence = harness.execute_three_surface_workflow(
        plan,
        "http://example.invalid",
        pages,
        collector,
        {},
    )

    assert success is False
    assert executed == ["pin-contract-expectation", "reset-ui-workflow"]
    assert executed.count("reset-ui-workflow") == 1
    assert evidence["executed_step_count"] == 2
    assert evidence["retry"] is False
    assert evidence["rewrite_expectation"] is False
    assert harness.THREE_SURFACE_PRECONDITION_DIGEST == (
        "sha256:67668370769a7a7f81c820550d4a10033bde8e297b2da1d05d55819cade90873"
    )


class _FakeStartCombatPage(_FakePage):
    def __init__(self):
        super().__init__()
        self.events = []
        self.click_calls = []
        self.response_predicate = None

    def wait_for_selector(self, selector, **kwargs):
        self.events.append(("wait", selector, kwargs))

    def click(self, selector):
        self.events.append(("click", selector))
        self.click_calls.append(selector)

    def expect_response(self, predicate):
        self.events.append(("expect-response",))
        self.response_predicate = predicate
        events = self.events

        class _ResponseContext:
            def __enter__(self):
                events.append(("response-enter",))
                return self

            def __exit__(self, exc_type, exc, traceback):
                events.append(("response-exit",))
                return False

        return _ResponseContext()


def _execute_start_combat_step(harness, page):
    plan = harness.build_three_surface_workflow_plan()
    step = next(item for item in plan["steps"] if item["step_id"] == "start-combat")
    harness._execute_three_surface_step(
        step,
        plan,
        "http://example.invalid",
        {"dm": page},
        None,
        {},
        {},
    )


def test_three_surface_start_combat_closes_toolbox_before_single_start_click():
    harness = _load_browser_smoke_harness()
    page = _FakeStartCombatPage()

    _execute_start_combat_step(harness, page)

    assert page.click_calls == ["#closeToolboxBtn", "#startCombatBtn"]


def test_three_surface_start_combat_uses_normal_clicks_without_force_or_dom_bypass():
    harness = _load_browser_smoke_harness()
    page = _FakeStartCombatPage()

    _execute_start_combat_step(harness, page)

    assert page.click_calls == ["#closeToolboxBtn", "#startCombatBtn"]
    assert not hasattr(page, "evaluate")
    assert not hasattr(page, "dispatch_event")


def test_three_surface_start_combat_waits_for_successful_response_before_returning():
    harness = _load_browser_smoke_harness()
    page = _FakeStartCombatPage()

    _execute_start_combat_step(harness, page)

    event_names = [event[0] for event in page.events]
    assert event_names.index("response-enter") < page.events.index(("click", "#startCombatBtn"))
    assert event_names.index("response-exit") > page.events.index(("click", "#startCombatBtn"))

    class _Request:
        method = "POST"

    class _Response:
        request = _Request()
        url = "http://example.invalid/api/dm/combat/start"
        ok = True

    assert page.response_predicate(_Response()) is True


class _FakeJsonResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def test_three_surface_runtime_actions_follow_live_authoritative_order():
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    steps = [dict(step) for step in plan["steps"]]
    fixture = _complete_three_surface_verification_response(harness)
    player_cids = list(fixture["player_cid_map"].values())
    enemy_cids = list(fixture["enemy_cid_map"].values())
    raven_cid = 301
    owl_cid = 302
    turn_order = [
        player_cids[0],
        raven_cid,
        enemy_cids[0],
        player_cids[1],
        owl_cid,
        *player_cids[2:],
        *enemy_cids[1:],
    ]
    payload = {
        "in_combat": True,
        "active_cid": turn_order[0],
        "turn_order": turn_order,
        "combatants": [
            {"cid": raven_cid, "name": "Raven", "role": "ally"},
            {"cid": owl_cid, "name": "Owl", "role": "ally"},
        ],
    }
    state = {
        "player_cid_map": fixture["player_cid_map"],
        "enemy_cid_map": fixture["enemy_cid_map"],
    }

    harness._order_three_surface_runtime_actions(
        steps,
        "http://example.invalid",
        {"three_surface_http_get": lambda *_args, **_kwargs: _FakeJsonResponse(payload)},
        state,
    )

    runtime_ids = state["runtime_turn_order_evidence"]["runtime_step_ids"]
    assert runtime_ids[:6] == [
        "player-attack-pc:dorian",
        "advance-player-turn-pc:dorian",
        f"advance-summon-turn-raven-{raven_cid}",
        "enemy-action-black-and-tan-captain",
        "advance-enemy-turn-black-and-tan-captain",
        "player-spell-pc:eldramar",
    ]
    assert state["runtime_turn_order_evidence"]["active_cid"] == player_cids[0]
    assert sorted(
        item["name"] for item in state["runtime_turn_order_evidence"]["skipped_summons"]
    ) == ["Owl", "Raven"]


def test_three_surface_mapped_positions_use_visible_canvas_geometry():
    harness = _load_browser_smoke_harness()

    class _CanvasLocator:
        def bounding_box(self):
            return {"x": 100, "y": 50, "width": 1000, "height": 700}

    class _GeometryPage:
        def __init__(self):
            self.waits = []

        def wait_for_selector(self, selector, **kwargs):
            self.waits.append((selector, kwargs))

        def locator(self, selector):
            assert selector == "#c"
            return _CanvasLocator()

    page = _GeometryPage()
    x, y = harness._mapped_screen_position(
        page,
        "#c",
        {"col": 16, "row": 12},
        "mapped-position",
        {"cols": 30, "rows": 20},
        32,
    )

    assert 100 <= x <= 1100
    assert 50 <= y <= 750
    assert page.waits == [("#c", {"state": "visible", "timeout": 10000})]
    assert not hasattr(page, "evaluate")


def test_three_surface_turn_alert_interacts_only_with_visible_modal():
    harness = _load_browser_smoke_harness()

    class _VisibleState:
        def __init__(self, visible):
            self.visible = visible

        def is_visible(self):
            return self.visible

    class _TurnAlertPage:
        def __init__(self):
            self.visible = False
            self.clicks = []

        def wait_for_timeout(self, timeout):
            assert timeout == 250

        def locator(self, selector):
            assert selector == "#turnModal.show"
            return _VisibleState(self.visible)

        def wait_for_selector(self, selector, **_kwargs):
            assert selector == "#turnModalOk"

        def click(self, selector):
            self.clicks.append(selector)

    page = _TurnAlertPage()
    harness._dismiss_visible_turn_alert(page, "turn-alert")
    page.visible = True
    harness._dismiss_visible_turn_alert(page, "turn-alert")

    assert page.clicks == ["#turnModalOk"]


def test_three_surface_active_capabilities_use_keyword_wait_argument():
    harness = _load_browser_smoke_harness()
    expected_actions = [{"id": "baton", "executable": True}]

    class _CapabilityPage:
        def __init__(self):
            self.wait = None

        def wait_for_function(self, expression, *, arg, timeout):
            self.wait = (expression, arg, timeout)

        def evaluate(self, expression):
            assert expression == "window.__dmcontrolSmoke.availableActions()"
            return expected_actions

    page = _CapabilityPage()
    state = {
        "three_surface_http_get": lambda *_args, **_kwargs: _FakeJsonResponse({
            "ok": True,
            "summary": {
                "combatant_id": 119,
                "groups": {"actions": [{"id": "baton"}]},
            },
        }),
        "base_url": "http://example.invalid",
        "fixture_timeout_seconds": 30,
        "runtime_capability_sync": [],
    }

    actions = harness._wait_for_matching_dmcontrol_capabilities(
        page, 119, "enemy-action", state,
    )

    assert actions == expected_actions
    assert page.wait[1:] == ([119, ["baton"]], 10000)
    assert state["runtime_capability_sync"] == [
        {"cid": 119, "status_code": 200, "action_ids": ["baton"]}
    ]


def test_three_surface_target_selection_uses_nearest_in_range_enemy():
    harness = _load_browser_smoke_harness()
    positions = {
        enemy_slug: {"col": 20 + index, "row": 20 + index}
        for index, (enemy_slug, _name) in enumerate(harness.THREE_SURFACE_ENEMY_IDENTITIES)
    }
    nearest_slug = harness.THREE_SURFACE_ENEMY_IDENTITIES[-1][0]
    positions[nearest_slug] = {"col": 6, "row": 5}
    state = {
        "player_positions": {"pc:dorian": {"col": 5, "row": 5}},
        "enemy_positions": positions,
    }

    assert harness._nearest_three_surface_enemy_slug("pc:dorian", state) == nearest_slug


def test_three_surface_spell_plan_uses_visible_current_controls():
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    spell_steps = [
        step for step in plan["steps"]
        if step["action"] == "cast-spell-at-mapped-target"
    ]

    assert spell_steps
    assert all(step["selectors"] == (
        "#castSpellModalOpen",
        "#castSpellPresetList",
        ".cast-preview-cast-btn",
        "#c",
        "#spellResolveSubmit",
    ) for step in spell_steps)
    assert harness.THREE_SURFACE_TARGETED_SPELLS == {
        "pc:eldramar": "Fire Bolt",
        "pc:throat-goat": "Eldritch Blast",
        "pc:stikhiya": "Sacred Flame",
    }


def test_three_surface_noncaster_spell_step_falls_back_to_attack(monkeypatch):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    step = next(
        item for item in plan["steps"]
        if item["step_id"] == "player-spell-pc:john-twilight"
    )
    clicks = []
    mapped = []
    monkeypatch.setattr(harness, "_wait_for_visible", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness, "_dismiss_visible_turn_alert", lambda *_args: None)
    monkeypatch.setattr(harness, "_click_selector", lambda _page, selector, _step: clicks.append(selector))
    monkeypatch.setattr(harness, "_nearest_three_surface_enemy_slug", lambda *_args, **_kwargs: "enemy")
    monkeypatch.setattr(
        harness,
        "_click_mapped_position",
        lambda _page, selector, position, _step, grid, zoom: mapped.append(
            (selector, position, grid, zoom)
        ),
    )
    state = {
        "player_positions": {"pc:john-twilight": {"col": 1, "row": 1}},
        "enemy_positions": {"enemy": {"col": 2, "row": 2}},
        "grid": {"cols": 30, "rows": 20},
    }

    harness._execute_player_action(step, object(), state)

    assert clicks == ["#attackOverlayToggle", "#attackResolveSubmit"]
    assert mapped == [("#c", {"col": 2, "row": 2}, state["grid"], 32)]
    assert state["runtime_player_action_modes"][-1]["executed_action"] == "attack-mapped-target"


def test_three_surface_melee_attacks_drag_to_staging_position(monkeypatch):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    step = next(
        item for item in plan["steps"]
        if item["step_id"] == "player-attack-pc:dorian"
    )
    drags = []
    monkeypatch.setattr(harness, "_wait_for_visible", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness, "_dismiss_visible_turn_alert", lambda *_args: None)
    monkeypatch.setattr(harness, "_click_selector", lambda *_args: None)
    monkeypatch.setattr(harness, "_click_mapped_position", lambda *_args: None)
    monkeypatch.setattr(harness, "_nearest_three_surface_enemy_slug", lambda *_args, **_kwargs: "enemy")
    monkeypatch.setattr(
        harness,
        "_drag_mapped_position",
        lambda _page, selector, start, end, _step, grid, zoom: drags.append(
            (selector, start, end, grid, zoom)
        ),
    )

    class _MovementPage:
        def wait_for_timeout(self, timeout):
            assert timeout == 500

    state = {
        "player_positions": {"pc:dorian": {"col": 1, "row": 1}},
        "enemy_positions": {"enemy": {"col": 16, "row": 15}},
        "grid": {"cols": 30, "rows": 20},
    }

    harness._execute_player_action(step, _MovementPage(), state)

    assert drags == [(
        "#c",
        {"col": 1, "row": 1},
        harness.THREE_SURFACE_ATTACK_STAGING_POSITIONS["pc:dorian"],
        state["grid"],
        32,
    )]


def test_three_surface_player_action_waits_for_enabled_turn(monkeypatch):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    step = next(
        item for item in plan["steps"]
        if item["step_id"] == "player-attack-pc:fred"
    )
    waits = []
    monkeypatch.setattr(
        harness,
        "_wait_for_visible",
        lambda _page, selector, step_id, timeout=10000: waits.append(
            (selector, step_id, timeout)
        ),
    )
    monkeypatch.setattr(harness, "_dismiss_visible_turn_alert", lambda *_args: None)
    monkeypatch.setattr(harness, "_click_selector", lambda *_args: None)
    monkeypatch.setattr(harness, "_click_mapped_position", lambda *_args: None)
    monkeypatch.setattr(harness, "_nearest_three_surface_enemy_slug", lambda *_args, **_kwargs: "enemy")
    state = {
        "player_positions": {"pc:fred": {"col": 1, "row": 1}},
        "enemy_positions": {"enemy": {"col": 2, "row": 2}},
        "grid": {"cols": 30, "rows": 20},
    }

    harness._execute_player_action(step, object(), state)

    assert waits[0] == ("#endTurn:not([disabled])", "player-attack-pc:fred", 10000)


def test_three_surface_successful_spell_save_is_immediate_result():
    harness = _load_browser_smoke_harness()

    class _SpellLocator:
        def __init__(self, *, visible=False, text=""):
            self.visible = visible
            self.text = text

        def is_visible(self):
            return self.visible

        def text_content(self):
            return self.text

    class _ImmediateSavePage:
        def __init__(self):
            self.modal = _SpellLocator(visible=False)
            self.note = _SpellLocator(text="Sacred Flame: target saved successfully")

        def locator(self, selector):
            return self.modal if selector == "#spellResolveModal.show" else self.note

        def wait_for_timeout(self, _timeout):
            raise AssertionError("immediate result should not poll again")

    harness._finish_targeted_spell(
        _ImmediateSavePage(),
        "#spellResolveSubmit",
        "Sacred Flame",
        "player-spell-pc:stikhiya",
    )


def test_three_surface_spell_attack_waits_for_attack_resolution_modal():
    harness = _load_browser_smoke_harness()

    class _SpellLocator:
        def __init__(self, *, visible=False, text=""):
            self.visible = visible
            self.text = text

        def is_visible(self):
            return self.visible

        def text_content(self):
            return self.text

    class _DelayedAttackResolutionPage:
        def __init__(self):
            self.attack_modal = _SpellLocator(visible=False)
            self.spell_modal = _SpellLocator(visible=False)
            self.target_selection_confirm = _SpellLocator(visible=False)
            self.note = _SpellLocator(text="Casted Fire Bolt.")
            self.clicks = []
            self.polls = []

        def locator(self, selector):
            return {
                "#attackResolveModal.show": self.attack_modal,
                "#spellResolveModal.show": self.spell_modal,
                "#spellTargetSelectionConfirm:not([disabled])": self.target_selection_confirm,
                "#note": self.note,
            }[selector]

        def wait_for_timeout(self, timeout):
            self.polls.append(timeout)
            self.attack_modal.visible = True

        def wait_for_selector(self, selector, **_kwargs):
            assert selector == "#attackResolveSubmit"

        def click(self, selector):
            self.clicks.append(selector)

    page = _DelayedAttackResolutionPage()
    harness._finish_targeted_spell(
        page,
        "#spellResolveSubmit",
        "Fire Bolt",
        "player-spell-pc:eldramar",
    )

    assert page.polls == [100]
    assert page.clicks == ["#attackResolveSubmit"]


def test_three_surface_multi_target_spell_confirms_visible_target_selection():
    harness = _load_browser_smoke_harness()

    class _SpellLocator:
        def __init__(self, *, visible=False, text=""):
            self.visible = visible
            self.text = text

        def is_visible(self):
            return self.visible

        def text_content(self):
            return self.text

    class _MultiTargetSpellPage:
        def __init__(self):
            self.attack_modal = _SpellLocator(visible=False)
            self.spell_modal = _SpellLocator(visible=False)
            self.target_selection_confirm = _SpellLocator(visible=True)
            self.note = _SpellLocator(text="Select targets (0/3) for Eldritch Blast.")
            self.clicks = []

        def locator(self, selector):
            return {
                "#attackResolveModal.show": self.attack_modal,
                "#spellResolveModal.show": self.spell_modal,
                "#spellTargetSelectionConfirm:not([disabled])": self.target_selection_confirm,
                "#note": self.note,
            }[selector]

        def wait_for_selector(self, selector, **_kwargs):
            assert selector in {
                "#spellTargetSelectionConfirm:not([disabled])",
                "#attackResolveSubmit",
            }

        def click(self, selector):
            self.clicks.append(selector)
            if selector == "#spellTargetSelectionConfirm:not([disabled])":
                self.target_selection_confirm.visible = False
                self.attack_modal.visible = True

        def wait_for_timeout(self, _timeout):
            raise AssertionError("visible target selection should advance without polling")

    page = _MultiTargetSpellPage()
    harness._finish_targeted_spell(
        page,
        "#spellResolveSubmit",
        "Eldritch Blast",
        "player-spell-pc:throat-goat",
    )

    assert page.clicks == [
        "#spellTargetSelectionConfirm:not([disabled])",
        "#attackResolveSubmit",
    ]


def test_three_surface_enemy_action_waits_for_dmcontrol_active_cid(monkeypatch):
    harness = _load_browser_smoke_harness()
    plan = harness.build_three_surface_workflow_plan()
    step = next(
        item for item in plan["steps"]
        if item["step_id"] == "enemy-action-black-and-tan-captain"
    )
    expected_cid = 286
    barriers = []
    monkeypatch.setattr(
        harness,
        "_wait_for_matching_dmcontrol_capabilities",
        lambda _page, cid, step_id, _state: (
            barriers.append((cid, step_id))
            or [{"id": "pistol", "executable": True}]
        ),
    )
    monkeypatch.setattr(harness, "_wait_for_visible", lambda *_args, **_kwargs: None)

    class _EnemyPage:
        def evaluate(self, expression, *_args):
            if expression == "window.__dmcontrolSmoke.targetPreviewMode()":
                return {"active": False}
            if expression == "window.__dmcontrolSmoke.aoeState()":
                return {"active": False}
            if expression == "window.__dmcontrolSmoke.modalSummary()":
                return {"active": False}
            return None

    harness._execute_enemy_action(
        step,
        _EnemyPage(),
        {"enemy_cid_map": {step["enemy_slug"]: expected_cid}},
    )

    assert barriers == [(expected_cid, step["step_id"])]


def test_three_surface_summon_advance_waits_for_active_transition():
    harness = _load_browser_smoke_harness()
    events = []

    class _SummonPage:
        def wait_for_function(self, expression, *, arg, timeout):
            events.append(("wait", expression, arg, timeout))

        def evaluate(self, expression):
            events.append(("evaluate", expression))

    step = {
        "step_id": "advance-summon-turn-raven-306",
        "surface": "/dmcontrol",
        "action": "advance-verified-summon",
        "runtime_cid": 306,
    }
    harness._execute_three_surface_step(
        step,
        {"steps": [step]},
        "http://example.invalid",
        {"dmcontrol": _SummonPage()},
        None,
        {},
        {},
    )

    assert events[0][0] == "wait"
    assert events[0][2:] == (306, 10000)
    assert events[1] == ("evaluate", "handleCombatControl()")

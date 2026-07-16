#!/usr/bin/env python3
"""
Browser Smoke Harness (Gate 4)
Provides the CLI and artifact collection foundation for automated browser smoke tests.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from playwright.sync_api import sync_playwright, Page, BrowserContext, Browser

# Constants
DEFAULT_ARTIFACT_ROOT = Path("logs/browser-smoke")
DEFAULT_BASE_URL = "http://localhost:8787"
THREE_SURFACE_SCENARIO_ID = "black-tan-three-surface-workflow"
THREE_SURFACE_SCHEMA_VERSION = "a7-ui-reset-contract/v1"
THREE_SURFACE_RESET_VERSION = "blank-combat/v1"
THREE_SURFACE_PRECONDITION_DIGEST = (
    "sha256:67668370769a7a7f81c820550d4a10033bde8e297b2da1d05d55819cade90873"
)
THREE_SURFACE_PLAYER_IDENTITIES = (
    ("pc:dorian", "Dorian"),
    ("pc:eldramar", "Eldramar"),
    ("pc:fred", "Fred"),
    ("pc:john-twilight", "John Twilight"),
    ("pc:johnny-morris", "Johnny Morris"),
    ("pc:malagrou", "Malagrou"),
    ("pc:old-man", "Old Man"),
    ("pc:throat-goat", "Throat Goat"),
    ("pc:vicnor", "Vicnor"),
    ("pc:stikhiya", "стихия"),
)
THREE_SURFACE_ENEMY_IDENTITIES = (
    ("black-and-tan-captain", "Black and Tan Captain"),
    ("black-and-tan-constable", "Black and Tan Constable"),
    ("black-and-tan-field-medic", "Black and Tan Field Medic"),
    ("black-and-tan-lieutenant", "Black and Tan Lieutenant"),
    ("black-and-tan-major", "Black and Tan Major"),
    ("black-and-tan-rifleman", "Black and Tan Rifleman"),
    ("black-and-tan-vda-scorcher", "Black and Tan VDA Scorcher"),
    ("black-and-tan-shield-trooper", "Black and Tan Shield Trooper"),
    ("black-and-tan-suppression-gunner", "Black and Tan Suppression Gunner"),
)


def _three_surface_players() -> List[Dict[str, str]]:
    return [
        {"player_id": player_id, "name": name}
        for player_id, name in THREE_SURFACE_PLAYER_IDENTITIES
    ]


def _three_surface_enemies() -> List[Dict[str, str]]:
    return [
        {"enemy_slug": enemy_slug, "name": name}
        for enemy_slug, name in THREE_SURFACE_ENEMY_IDENTITIES
    ]


def three_surface_fixture_request(operation: str) -> Dict[str, Any]:
    if operation not in ("reset-ui-workflow", "verify-ui-workflow"):
        raise ValueError(f"Unsupported three-surface fixture operation: {operation}")
    return {
        "schema_version": THREE_SURFACE_SCHEMA_VERSION,
        "operation": operation,
        "reset_version": THREE_SURFACE_RESET_VERSION,
        "expected_precondition_digest": THREE_SURFACE_PRECONDITION_DIGEST,
        "players": _three_surface_players(),
        "enemies": _three_surface_enemies(),
    }


def build_three_surface_workflow_plan() -> Dict[str, Any]:
    """Build the stable G1B-proven selector/API plan without touching a browser."""
    steps: List[Dict[str, Any]] = []

    def add_step(step_id: str, surface: str, action: str, **details: Any) -> None:
        steps.append({
            "order": len(steps) + 1,
            "step_id": step_id,
            "surface": surface,
            "action": action,
            **details,
        })

    add_step(
        "pin-contract-expectation",
        "fixture",
        "validate-expectation",
        browser_interaction=False,
        required_versions={
            "schema_version": THREE_SURFACE_SCHEMA_VERSION,
            "reset_version": THREE_SURFACE_RESET_VERSION,
            "precondition_digest": THREE_SURFACE_PRECONDITION_DIGEST,
        },
        required_mappings=("player_cid_map", "enemy_cid_map", "players.position", "enemies.position"),
    )
    add_step(
        "reset-ui-workflow",
        "fixture",
        "post-json",
        browser_interaction=False,
        path="/api/dev/smoke-fixtures/black-tan-combat-exploration",
        request=three_surface_fixture_request("reset-ui-workflow"),
    )
    add_step(
        "validate-reset-contract",
        "fixture",
        "terminal-contract-barrier",
        browser_interaction=False,
        terminal_reasons=("fixture-precondition-mismatch", "ui-setup-mismatch"),
        retry=False,
        rewrite_expectation=False,
    )
    add_step("navigate-dm", "/dm", "goto", path="/dm")
    add_step("open-toolbox", "/dm", "click", selector="#openToolboxBtn")
    add_step("open-encounter", "/dm", "click", selector="#tab-encounter")
    add_step(
        "select-all-roster-players",
        "/dm",
        "click",
        root_selector="#encounterPlayerList",
        selector="#selectAllPlayersBtn",
        expected_players=_three_surface_players(),
    )
    add_step("add-all-roster-players", "/dm", "click", selector="#addPlayersBtn")
    for enemy_slug, enemy_name in THREE_SURFACE_ENEMY_IDENTITIES:
        add_step(
            f"add-enemy-{enemy_slug}",
            "/dm",
            "select-and-click",
            selector="#monsterSlugSelect",
            value=enemy_slug,
            count_selector="#monsterCount",
            count=1,
            ally_selector="#monsterAlly",
            ally=False,
            submit_selector="#addMonsterBtn",
            expected_name=enemy_name,
        )
    add_step("start-combat", "/dm", "click", selector="#startCombatBtn")
    add_step(
        "verify-ui-workflow",
        "fixture",
        "post-json",
        browser_interaction=False,
        path="/api/dev/smoke-fixtures/black-tan-combat-exploration",
        request=three_surface_fixture_request("verify-ui-workflow"),
    )
    add_step(
        "validate-complete-runtime-mappings",
        "fixture",
        "terminal-contract-barrier",
        browser_interaction=False,
        required_player_ids=[player_id for player_id, _name in THREE_SURFACE_PLAYER_IDENTITIES],
        required_enemy_slugs=[enemy_slug for enemy_slug, _name in THREE_SURFACE_ENEMY_IDENTITIES],
        require_positions=True,
        retry=False,
        rewrite_expectation=False,
    )
    add_step("navigate-dmcontrol", "/dmcontrol", "goto", path="/dmcontrol")
    for player_id, _name in THREE_SURFACE_PLAYER_IDENTITIES:
        add_step(f"navigate-player-{player_id}", "/", "goto", path="/", player_id=player_id)
        add_step(
            f"claim-player-{player_id}",
            "/",
            "claim-mapped-player",
            player_id=player_id,
            selector_template='#claimList [data-claim-cid="<cid>"]',
            confirm_selector="#claimConfirm",
            identity_selector="#me",
        )

    for index, (player_id, _name) in enumerate(THREE_SURFACE_PLAYER_IDENTITIES):
        if index % 2 == 0:
            add_step(
                f"player-attack-{player_id}",
                "/",
                "attack-mapped-target",
                player_id=player_id,
                selectors=("#attackOverlayToggle", "#c", "#attackResolveSubmit"),
                target_mapping="enemy_slug_to_cid_and_position",
            )
        else:
            add_step(
                f"player-spell-{player_id}",
                "/",
                "cast-spell-at-mapped-target",
                player_id=player_id,
                selectors=(
                    "#castSpellModalOpen", "#castPreset", "#castName", "#castSlotLevel",
                    "#castSubmit", "#c", "#spellResolveSubmit",
                ),
                target_mapping="enemy_slug_to_cid_and_position",
            )
        add_step(f"advance-player-turn-{player_id}", "/", "click", selector="#endTurn", player_id=player_id)

    for enemy_slug, _name in THREE_SURFACE_ENEMY_IDENTITIES:
        add_step(
            f"enemy-action-{enemy_slug}",
            "/dmcontrol",
            "execute-active-action",
            enemy_slug=enemy_slug,
            smoke_apis=(
                "window.__dmcontrolSmoke.availableActions()",
                "selectCapability(id)",
                "startSequence(id)",
                "window.__dmcontrolSmoke.modalSummary()",
            ),
            action_selector_template='[data-testid="dmcontrol-action-card-<capability-id>"]',
            apply_selector="#modalApplyBtn",
            target_mapping="player_id_to_cid_and_position",
        )
        add_step(
            f"advance-enemy-turn-{enemy_slug}",
            "/dmcontrol",
            "evaluate",
            smoke_api="handleCombatControl()",
            enemy_slug=enemy_slug,
        )

    add_step(
        "assert-dm-visible-state",
        "/dm",
        "assert-visible-state",
        selectors=("#combatBadge", "#roundVal", "#turnVal", "#activeName", "#upNextName", "#combatantList .combatant-row[data-cid]"),
    )
    add_step(
        "assert-dmcontrol-visible-state",
        "/dmcontrol",
        "assert-visible-state",
        selectors=("#combatStatus", '[data-testid="dmcontrol-map-canvas"]', '[data-testid="dmcontrol-active-actor-panel"]'),
        smoke_apis=("window.__dmcontrolSmoke.state()", "window.__dmcontrolSmoke.roundOrTurn()"),
    )
    add_step(
        "assert-player-visible-state",
        "/",
        "assert-visible-state",
        selectors=("#connFullText", "#me", "#turn", "#playerHpBarLabel", "#action", "#mapViewTurnOrder", "#mapViewTurnOrderStatus", "#c"),
    )

    return {
        "scenario_id": THREE_SURFACE_SCENARIO_ID,
        "surfaces": (
            {"role": "dm", "path": "/dm"},
            {"role": "dmcontrol", "path": "/dmcontrol"},
            {"role": "player", "path": "/"},
        ),
        "contract": three_surface_fixture_request("verify-ui-workflow"),
        "ordered_players": _three_surface_players(),
        "ordered_enemies": _three_surface_enemies(),
        "round_policy": {
            "rounds": 1,
            "runtime_actor_resolution": "strict pinned identity/CID maps",
            "player_action_pattern": "attack,spell alternating by ordered player identity",
            "enemy_action_policy": "first executable action from verified smoke API",
        },
        "steps": steps,
    }


def _bounded_failure_detail(value: Any, limit: int = 512) -> str:
    if isinstance(value, str):
        detail = value
    else:
        detail = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return detail if len(detail) <= limit else f"{detail[:limit - 3]}..."


def validate_three_surface_fixture_contract(
    response: Dict[str, Any],
    operation: str,
) -> Dict[str, Any]:
    """Strictly validate a reset/verify response against pinned expectations."""
    expected_players = _three_surface_players()
    expected_enemies = _three_surface_enemies()
    mismatches: List[str] = []

    if not isinstance(response, dict):
        response = {}
        mismatches.append("response:not-object")
    for field, expected in (
        ("schema_version", THREE_SURFACE_SCHEMA_VERSION),
        ("reset_version", THREE_SURFACE_RESET_VERSION),
        ("precondition_digest", THREE_SURFACE_PRECONDITION_DIGEST),
        ("operation", operation),
    ):
        if response.get(field) != expected:
            mismatches.append(f"{field}:mismatch")

    raw_players = response.get("players")
    raw_enemies = response.get("enemies")
    if operation == "reset-ui-workflow":
        if raw_players != expected_players:
            mismatches.append("players:ordered-identity-mismatch")
        if raw_enemies != expected_enemies:
            mismatches.append("enemies:ordered-identity-mismatch")
        if any(response.get(field) != 0 for field in ("player_count", "enemy_count", "combatant_count")):
            mismatches.append("counts:expected-zero")
        if response.get("player_cid_map") != {} or response.get("enemy_cid_map") != {}:
            mismatches.append("mappings:expected-empty")
        if response.get("mutated") is not True or response.get("in_combat") is not False:
            mismatches.append("reset-state:mismatch")
    elif operation == "verify-ui-workflow":
        player_projection = [
            {"player_id": item.get("player_id"), "name": item.get("name")}
            for item in raw_players
        ] if isinstance(raw_players, list) else []
        enemy_projection = [
            {"enemy_slug": item.get("enemy_slug"), "name": item.get("name")}
            for item in raw_enemies
        ] if isinstance(raw_enemies, list) else []
        if player_projection != expected_players:
            mismatches.append("players:ordered-identity-mismatch")
        if enemy_projection != expected_enemies:
            mismatches.append("enemies:ordered-identity-mismatch")
        if response.get("player_count") != 10 or response.get("enemy_count") != 9 or response.get("combatant_count") != 19:
            mismatches.append("counts:mismatch")
        player_map = response.get("player_cid_map")
        enemy_map = response.get("enemy_cid_map")
        expected_player_ids = [player_id for player_id, _name in THREE_SURFACE_PLAYER_IDENTITIES]
        expected_enemy_slugs = [enemy_slug for enemy_slug, _name in THREE_SURFACE_ENEMY_IDENTITIES]
        if not isinstance(player_map, dict) or list(player_map) != expected_player_ids:
            mismatches.append("player_cid_map:incomplete-or-unordered")
        if not isinstance(enemy_map, dict) or list(enemy_map) != expected_enemy_slugs:
            mismatches.append("enemy_cid_map:incomplete-or-unordered")
        seen_cids: List[int] = []
        for collection, identity_key, mapping in (
            (raw_players, "player_id", player_map),
            (raw_enemies, "enemy_slug", enemy_map),
        ):
            if not isinstance(collection, list) or not isinstance(mapping, dict):
                continue
            for item in collection:
                cid = item.get("cid") if isinstance(item, dict) else None
                position = item.get("position") if isinstance(item, dict) else None
                identity = item.get(identity_key) if isinstance(item, dict) else None
                if isinstance(cid, bool) or not isinstance(cid, int) or mapping.get(identity) != cid:
                    mismatches.append(f"{identity_key}:cid-mismatch")
                    continue
                seen_cids.append(cid)
                if not isinstance(position, dict) or any(
                    isinstance(position.get(axis), bool) or not isinstance(position.get(axis), int)
                    for axis in ("col", "row")
                ):
                    mismatches.append(f"{identity_key}:position-mismatch")
        if len(seen_cids) != 19 or len(set(seen_cids)) != 19:
            mismatches.append("runtime_cids:not-complete-and-unique")
        if response.get("mutated") is not False:
            mismatches.append("verification:must-not-mutate")
    else:
        mismatches.append("operation:unsupported")

    if mismatches:
        reason = "ui-setup-mismatch" if response.get("error") == "ui_setup_mismatch" else "fixture-precondition-mismatch"
        return {
            "ok": False,
            "terminal": True,
            "terminal_classification": "fail",
            "reason": reason,
            "retry": False,
            "rewrite_expectation": False,
            "later_workflow_steps": 0,
            "failure_detail": _bounded_failure_detail(mismatches[:12]),
        }
    return {
        "ok": True,
        "terminal": False,
        "terminal_classification": "continue",
        "reason": None,
        "retry": False,
        "rewrite_expectation": False,
    }


def classify_three_surface_contract_response(response: Dict[str, Any], operation: str) -> Dict[str, Any]:
    if isinstance(response, dict) and response.get("ok") is False:
        error = response.get("error")
        reason = "ui-setup-mismatch" if error == "ui_setup_mismatch" else "fixture-precondition-mismatch"
        return {
            "ok": False,
            "terminal": True,
            "terminal_classification": "fail",
            "reason": reason,
            "retry": False,
            "rewrite_expectation": False,
            "later_workflow_steps": 0,
            "failure_detail": _bounded_failure_detail({
                "error": error or "contract_mismatch",
                "mismatch_details": response.get("mismatch_details", [])[:8]
                if isinstance(response.get("mismatch_details"), list) else [],
            }),
        }
    return validate_three_surface_fixture_contract(response, operation)


def build_three_surface_evidence(
    *,
    run_id: str,
    terminal_classification: str,
    step_timings: List[Dict[str, Any]],
    screenshots: Optional[List[str]] = None,
    browser_trace: Optional[str] = None,
    server_log: Optional[str] = None,
    debug_trace: Optional[str] = None,
    fixture_evidence: Optional[Dict[str, Any]] = None,
    port_ownership: Optional[Dict[str, Any]] = None,
    cleanup_disposition: Optional[Dict[str, Any]] = None,
    failure_detail: Any = "",
    role_traces: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "evidence_schema_version": "a7-three-surface-evidence/v1",
        "task_id": "CODEX-20260715-a7-browser-contract-implementation-g1c",
        "gate_id": "A7-G1C",
        "scenario_id": THREE_SURFACE_SCENARIO_ID,
        "run_id": str(run_id),
        "terminal_classification": terminal_classification,
        "ordered_step_timings": list(step_timings),
        "artifacts": {
            "screenshots": list(screenshots or []),
            "browser_trace": browser_trace,
            "server_log": server_log,
            "debug_trace": debug_trace,
            "role_traces": dict(role_traces or {}),
        },
        "fixture_evidence": dict(fixture_evidence or {}),
        "port_ownership": dict(port_ownership or {}),
        "cleanup_disposition": dict(cleanup_disposition or {}),
        "failure_detail": _bounded_failure_detail(failure_detail),
    }


def cleanup_owned_process(process: Any, ownership: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Stop only a process whose PID is positively tied to this harness handle."""
    process_pid = getattr(process, "pid", None) if process is not None else None
    verified = bool(ownership and ownership.get("verified") is True)
    owned_pid = ownership.get("pid") if isinstance(ownership, dict) else None
    if process is None:
        return {"status": "no-owned-process", "cleaned": False}
    if not verified or process_pid is None or owned_pid != process_pid:
        return {
            "status": "refused-unverified-process-ownership",
            "cleaned": False,
            "pid": process_pid,
        }
    if process.poll() is not None:
        return {"status": "owned-process-already-exited", "cleaned": False, "pid": process_pid}

    process.terminate()
    try:
        process.wait(timeout=5)
        forced = False
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        forced = True
    return {
        "status": "owned-process-cleaned",
        "cleaned": True,
        "forced": forced,
        "pid": process_pid,
    }

@dataclass
class BrowserRole:
    """Represents a browser instance role in a scenario."""
    name: str  # e.g., 'dm', 'player1'
    context_metadata: Dict[str, Any] = field(default_factory=dict)


class Scenario:
    """Base class for all smoke scenarios."""
    def __init__(self, id: str, description: str):
        self.id = id
        self.description = description
        self.roles: List[BrowserRole] = []

    def run(self, base_url: str, pages: Dict[str, Page], collector: ArtifactCollector, config: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        """Runs the scenario. To be implemented by subclasses in Gate 4+."""
        raise NotImplementedError(f"Scenario '{self.id}' not implemented")


class BlackTanThreeSurfaceWorkflowScenario(Scenario):
    """Data-first A7 plan; execution remains an explicitly injected later-gate concern."""

    def __init__(self):
        super().__init__(
            THREE_SURFACE_SCENARIO_ID,
            "Black and Tan deterministic /dm, /dmcontrol, and / workflow",
        )
        self.roles = [
            BrowserRole("dm", {"path": "/dm"}),
            BrowserRole("dmcontrol", {"path": "/dmcontrol"}),
            *[
                BrowserRole(f"player:{player_id}", {"path": "/", "player_id": player_id})
                for player_id, _name in THREE_SURFACE_PLAYER_IDENTITIES
            ],
        ]
        self.plan = build_three_surface_workflow_plan()

    def run(self, base_url: str, pages: Dict[str, Page], collector: ArtifactCollector, config: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        executor = config.get("three_surface_executor")
        if not callable(executor):
            evidence = build_three_surface_evidence(
                run_id=collector.timestamp,
                terminal_classification="fail",
                step_timings=[],
                screenshots=collector.screenshots,
                failure_detail="three-surface-executor-not-authorized-or-configured",
                cleanup_disposition={"status": "no-owned-process", "cleaned": False},
            )
            return False, evidence
        return executor(self.plan, base_url, pages, collector, config)

class ScorcherIgniteGroundScenario(Scenario):
    """
    Scenario for Black and Tan VDA Scorcher Ignite Ground pilot.
    """
    def __init__(self):
        super().__init__("scorcher-ignite-ground", "Black and Tan VDA Scorcher Ignite Ground pilot")
        self.roles = [BrowserRole("dm")]

    def run(self, base_url: str, pages: Dict[str, Page], collector: ArtifactCollector, config: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        page = pages["dm"]

        # 1. POST to fixture
        logging.info("Seeding Scorcher fixture...")
        try:
            resp = requests.post(f"{base_url}/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground", timeout=10)
            resp.raise_for_status()
            fixture_data = resp.json()
        except Exception as e:
            logging.error(f"Fixture request failed: {e}")
            return False, {}

        if not fixture_data.get("ok"):
            logging.error(f"Fixture returned error: {fixture_data.get('error')}")
            return False, {}

        actor_cid = fixture_data["actor_cid"]
        logging.info(f"Fixture seeded. Actor CID: {actor_cid}")

        # 2. Navigate to /dmcontrol
        logging.info("Navigating to /dmcontrol...")
        page.goto(f"{base_url}/dmcontrol?smoke=1", wait_until="domcontentloaded")

        # 3. Wait for readiness
        logging.info("Waiting for window.__dmcontrolSmoke.ready()...")
        page.wait_for_function("window.__dmcontrolSmoke && window.__dmcontrolSmoke.ready()", timeout=15000)

        # 4. Verify active actor
        active_cid = page.evaluate("window.__dmcontrolSmoke.activeActorCid()")
        if str(active_cid) != str(actor_cid):
             logging.error(f"Active actor mismatch: expected {actor_cid}, got {active_cid}")
             collector.capture_screenshot(page, "fail_actor_mismatch")
             return False, {}

        # 5. Select Ignite Ground
        logging.info("Selecting Ignite Ground action...")
        action_card_selector = "[data-testid='dmcontrol-action-card-ignite-ground']"
        page.wait_for_selector(action_card_selector, state="visible", timeout=10000)

        # Selection logic: direct call + click for maximum reliability in headless
        page.evaluate("""(id) => {
            if (typeof selectCapability === 'function') selectCapability(id);
            // Backup in case selectCapability toggled or failed
            selectedCapabilityId = id;
            if (typeof renderActionPanel === 'function') {
                const actor = (state.combatants || []).find(c => String(c.cid) === String(state.active_cid));
                renderActionPanel(actor, capabilitySummary);
            }
        }""", "ignite-ground")

        # 6. Verify selected action
        logging.info("Verifying selected action...")
        page.wait_for_function("window.__dmcontrolSmoke.selectedAction() === 'ignite-ground'", timeout=5000)

        # 7. Click deterministic map location (8,8)
        logging.info("Clicking map at (8,8)...")
        # Grid to client coordinates
        coords = page.evaluate("""() => {
            const col = 8;
            const row = 8;
            return {
                x: col * zoom + panX + zoom/2,
                y: row * zoom + panY + zoom/2
            };
        }""")

        # Move and click
        page.mouse.move(coords["x"], coords["y"])
        page.mouse.down()
        page.mouse.up()

        # 8. Verify result modal opens
        logging.info("Verifying result modal...")
        page.wait_for_function("window.__dmcontrolSmoke.isModalOpen()", timeout=5000)

        # 9. Verify affected target count is 0
        target_count_selector = "[data-testid='dmcontrol-aoe-affected-count']"
        page.wait_for_selector(target_count_selector, state="visible", timeout=5000)
        target_count_text = page.locator(target_count_selector).inner_text()
        if "(0)" not in target_count_text.upper():
            logging.error(f"Expected 0 targets, got: {target_count_text}")
            collector.capture_screenshot(page, "fail_target_count")
            return False, {}

        initial_hazard_count = page.evaluate("window.__dmcontrolSmoke.hazardCount()")

        # 10. Click Apply Result
        logging.info("Clicking Apply Result...")
        # Note: The dynamic AoE modal currently overwrites the footer and might omit data-testid
        # but keeps id="modalApplyBtn".
        apply_btn_selector = "#modalApplyBtn"
        page.wait_for_selector(apply_btn_selector, state="visible", timeout=10000)
        page.evaluate(f"document.querySelector('{apply_btn_selector}').click()")

        # 11. Verify modal closes
        logging.info("Waiting for modal to close...")
        page.wait_for_function("!window.__dmcontrolSmoke.isModalOpen()", timeout=5000)

        # 12. Verify persistent hazard count increases
        # Wait a bit for the snapshot to update
        time.sleep(1)
        final_hazard_count = page.evaluate("window.__dmcontrolSmoke.hazardCount()")
        logging.info(f"Final hazard count: {final_hazard_count}")

        if final_hazard_count <= initial_hazard_count:
            logging.error(f"Hazard count did not increase: initial={initial_hazard_count}, final={final_hazard_count}")
            collector.capture_screenshot(page, "fail_hazard_count")
            return False, {}

        collector.capture_screenshot(page, "success_final")
        logging.info("Scenario scorcher-ignite-ground completed successfully.")
        return True, {}

class BlackTanCombatExplorationScenario(Scenario):
    """
    Scenario for AI/Browser-Driven Combat Bug Exploration (All Players vs All Black and Tans).
    """
    def __init__(self):
        super().__init__("black-tan-combat-exploration", "All Players vs All Black and Tans combat exploration")
        self.roles = [BrowserRole("dm")]

    def run(self, base_url: str, pages: Dict[str, Page], collector: ArtifactCollector, config: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        page = pages["dm"]
        max_rounds = config.get("max_rounds", 2)
        max_turns = config.get("max_turns", 100)
        slow_mo = config.get("slow_mo_ms", 0)

        # 1. POST to fixture
        logging.info("Seeding Black and Tan exploration fixture...")
        try:
            resp = requests.post(f"{base_url}/api/dev/smoke-fixtures/black-tan-combat-exploration", timeout=30)
            resp.raise_for_status()
            fixture_data = resp.json()
        except Exception as e:
            logging.error(f"Fixture request failed: {e}")
            return False, {}

        if not fixture_data.get("ok"):
            logging.error(f"Fixture returned error: {fixture_data.get('error')}")
            return False, {}

        logging.info(f"Fixture seeded: {fixture_data['player_count']} players, {fixture_data['monster_count']} monsters.")

        # 2. Navigate to /dmcontrol
        logging.info(f"Observer URL: {base_url}/dmcontrol")
        logging.info("Navigating to /dmcontrol...")
        page.goto(f"{base_url}/dmcontrol?smoke=1", wait_until="domcontentloaded")

        # 3. Wait for readiness
        logging.info("Waiting for window.__dmcontrolSmoke.ready()...")
        page.wait_for_function("window.__dmcontrolSmoke && window.__dmcontrolSmoke.ready()", timeout=15000)

        turn_count = 0
        events = []
        status = "pass"

        try:
            while turn_count < max_turns:
                # 4. Get current round/turn
                rt = page.evaluate("window.__dmcontrolSmoke.roundOrTurn()")
                current_round = rt["round"]
                if current_round > max_rounds:
                    logging.info(f"Reached max rounds ({max_rounds}). Stopping.")
                    break

                active_actor = page.evaluate("window.__dmcontrolSmoke.activeActorName()")
                active_cid = page.evaluate("window.__dmcontrolSmoke.activeActorCid()")
                logging.info(f"Round {current_round}, Turn {rt['turn']}: {active_actor} ({active_cid}) is active.")

                event = {
                    "turn": turn_count,
                    "round": current_round,
                    "actor": active_actor,
                    "cid": active_cid,
                    "actions": []
                }

                # 5. Execute Turn actions (potentially multiple steps)
                turn_step = 0
                max_turn_steps = 20 # Safety break

                while turn_step < max_turn_steps:
                    turn_step += 1

                    # 5a. Check for modal
                    modal = page.evaluate("window.__dmcontrolSmoke.modalSummary()")
                    if modal.get("active"):
                         logging.info(f"Modal active: {modal['title']}. Applying.")
                         event["actions"].append(f"apply-result: {modal['title']}")

                         apply_btn_selector = "#modalApplyBtn"
                         page.wait_for_selector(apply_btn_selector, state="visible", timeout=2000)
                         page.evaluate(f"document.querySelector('{apply_btn_selector}').click()")

                         # Wait for modal to close
                         page.wait_for_function("!window.__dmcontrolSmoke.modalSummary().active", timeout=5000)
                         time.sleep(0.5)
                         continue

                    # 5b. Check for AoE placement
                    aoe = page.evaluate("window.__dmcontrolSmoke.aoeState()")
                    if aoe.get("active"):
                         logging.info("Entering AoE targeting. Clicking (15, 15)")
                         event["actions"].append("aoe-click (15,15)")
                         coords = page.evaluate("""() => {
                            const col = 15;
                            const row = 15;
                            return {
                                x: col * zoom + panX + zoom/2,
                                y: row * zoom + panY + zoom/2
                            };
                        }""")
                         page.mouse.move(coords["x"], coords["y"])
                         page.mouse.down()
                         page.mouse.up()
                         time.sleep(0.5)
                         continue

                    # 5c. Check for single target selection
                    preview = page.evaluate("window.__dmcontrolSmoke.targetPreviewMode()")
                    if preview.get("active"):
                         logging.info("Entering Single Target mode. Clicking first candidate.")
                         target = page.evaluate("""() => {
                            const units = state?.tactical_map?.units || [];
                            const candidate = units.find(u => isTargetCandidate(u));
                            if (!candidate) return null;
                            return {
                                cid: candidate.cid,
                                col: candidate.pos.col,
                                row: candidate.pos.row
                            };
                         }""")
                         if target:
                            logging.info(f"Targeting candidate: {target['cid']} at ({target['col']}, {target['row']})")
                            event["actions"].append(f"target-click {target['cid']}")
                            coords = page.evaluate(f"""() => {{
                                const col = {target['col']};
                                const row = {target['row']};
                                return {{
                                    x: col * zoom + panX + zoom/2,
                                    y: row * zoom + panY + zoom/2
                                }};
                            }}""")
                            page.mouse.move(coords["x"], coords["y"])
                            page.mouse.down()
                            page.mouse.up()
                         else:
                            logging.warning("Single target mode active but no candidates found. Canceling.")
                            page.evaluate("cancelTargetPreviewMode()")

                         time.sleep(0.5)
                         continue

                    # 5d. Check for composite sequence
                    comp = page.evaluate("window.__dmcontrolSmoke.compositeState()")
                    if comp.get("active"):
                        sub_action = next((s for s in comp["steps"] if s["executable"]), None)
                        if sub_action:
                            logging.info(f"Selecting sequence step: {sub_action['name']} ({sub_action['id']})")
                            event["actions"].append(f"select-step {sub_action['id']}")
                            page.evaluate(f"selectCapability('{sub_action['id']}')")
                            time.sleep(0.5)
                            continue
                        else:
                            logging.info("Sequence active but no steps executable. Ending sequence.")
                            event["actions"].append("end-sequence")
                            page.evaluate("cancelLocalSequence()")
                            time.sleep(0.5)
                            continue

                    # 5e. If no mode active, pick a main action if none selected
                    selected_id = page.evaluate("window.__dmcontrolSmoke.selectedAction()")
                    if not selected_id:
                        actions = page.evaluate("window.__dmcontrolSmoke.availableActions()")
                        chosen_action = next((a for a in actions if a["executable"]), None)
                        if chosen_action:
                            logging.info(f"Selecting main action: {chosen_action['name']} ({chosen_action['id']})")
                            event["actions"].append(f"select {chosen_action['id']}")
                            page.evaluate(f"selectCapability('{chosen_action['id']}')")
                            time.sleep(0.5)

                            # Start sequence if composite
                            if chosen_action.get("action_type") == "composite":
                                logging.info(f"Starting composite sequence: {chosen_action['id']}")
                                event["actions"].append(f"start-sequence {chosen_action['id']}")
                                page.evaluate(f"startSequence('{chosen_action['id']}')")
                                time.sleep(0.5)
                            continue
                        else:
                            logging.warning(f"No executable actions available for {active_actor}.")
                            event["actions"].append("skip-actions")
                            break # Done with this turn
                    else:
                        # We have a selected action but no targeting/modal/sequence.
                        # This might be a simple action that didn't trigger anything,
                        # or we just finished an action.
                        logging.info(f"Action {selected_id} selected but no further mode active. Assuming turn done.")
                        break

                if turn_step >= max_turn_steps:
                    logging.warning(f"Turn sub-loop reached safety limit ({max_turn_steps}) for {active_actor}.")

                # 6. Next Turn
                logging.info("Advancing turn...")
                event["actions"].append("next-turn")
                page.evaluate("handleCombatControl()")
                time.sleep(1 + slow_mo/1000.0)

                # Wait for UI state to settle and be ready
                try:
                    page.wait_for_function("window.__dmcontrolSmoke.ready()", timeout=5000)
                except:
                    logging.error("Timeout waiting for smoke readiness after turn advancement.")
                    collector.capture_screenshot(page, f"timeout_turn_{turn_count}")
                    status = "fail"
                    events.append(event)
                    break

                events.append(event)
                turn_count += 1

            collector.capture_screenshot(page, "exploration_final")

            # Write per-turn event log
            event_log_path = collector.get_path("event_log.json")
            with open(event_log_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)

            # Record status summary
            summary_ext = {
                "turn_count": turn_count,
                "final_round": page.evaluate("window.__dmcontrolSmoke.roundOrTurn()")["round"],
                "event_log": str(event_log_path)
            }
            logging.info(f"Exploration finished after {turn_count} turns.")
            return status == "pass", summary_ext

        except Exception as e:
            logging.error(f"Exploration loop failed: {e}")
            collector.capture_screenshot(page, "fail_exploration")
            return False, {}

class Registry:
    """Registry of available smoke scenarios."""
    def __init__(self):
        self._scenarios: Dict[str, Scenario] = {}

    def register(self, scenario: Scenario):
        self._scenarios[scenario.id] = scenario

    def get(self, id: str) -> Optional[Scenario]:
        return self._scenarios.get(id)

    def list_all(self) -> List[Scenario]:
        return sorted(self._scenarios.values(), key=lambda s: s.id)

class ArtifactCollector:
    """Manages the creation and organization of test run artifacts."""
    def __init__(self, root: Path, scenario_id: str):
        self.root = root
        self.scenario_id = scenario_id
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.root / self.scenario_id / self.timestamp
        self._initialized = False
        self.screenshots: List[str] = []

    def ensure_initialized(self):
        if not self._initialized:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._initialized = True

    def write_summary(self, data: Dict[str, Any]):
        self.ensure_initialized()
        summary_path = self.run_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        summary_md_path = self.run_dir / "summary.md"
        with open(summary_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Smoke Test Summary: {self.scenario_id}\n\n")
            f.write(f"- **Status:** {data.get('status')}\n")
            f.write(f"- **Timestamp:** {data.get('timestamp')}\n")
            f.write(f"- **Roles:** {', '.join(data.get('roles', []))}\n")
            if data.get("error"):
                f.write(f"\n## Error\n\n```\n{data.get('error')}\n```\n")
            f.write("\n## Artifacts\n\n")
            for key, val in data.get("artifacts", {}).items():
                if isinstance(val, list):
                    f.write(f"- **{key}:**\n")
                    for item in val:
                        f.write(f"  - {item}\n")
                else:
                    f.write(f"- **{key}:** {val}\n")

    def get_path(self, filename: str) -> Path:
        self.ensure_initialized()
        return self.run_dir / filename

    def capture_screenshot(self, page: Page, name: str):
        self.ensure_initialized()
        path = self.run_dir / f"{name}.png"
        page.screenshot(path=path)
        self.screenshots.append(str(path))

class ServerHandle:
    """Abstraction for managing a tracker server instance."""
    def __init__(self, base_url: str, is_external: bool = True):
        self.base_url = base_url
        self.is_external = is_external
        self.process: Optional[subprocess.Popen] = None
        self.stdout_path: Optional[Path] = None
        self.stderr_path: Optional[Path] = None
        self.process_ownership: Dict[str, Any] = {
            "verified": False,
            "pid": None,
            "source": "external" if is_external else "not-started",
        }
        self.cleanup_disposition: Dict[str, Any] = {
            "status": "not-attempted",
            "cleaned": False,
        }

    def start(self, collector: Optional[ArtifactCollector] = None):
        if self.is_external:
            logging.info(f"Using external server at {self.base_url}")
            return

        logging.info("Starting local headless server...")
        env = os.environ.copy()
        env["INIT_TRACKER_DEBUGGING"] = "1"
        env["INIT_TRACKER_HEADLESS"] = "1"

        cmd = [sys.executable, "serve_headless.py", "--host", "127.0.0.1", "--port", "8787"]

        if collector:
            self.stdout_path = collector.get_path("server.stdout.log")
            self.stderr_path = collector.get_path("server.stderr.log")
            stdout_file = open(self.stdout_path, "w")
            stderr_file = open(self.stderr_path, "w")
        else:
            stdout_file = subprocess.PIPE
            stderr_file = subprocess.PIPE

        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True
        )
        self.process_ownership = {
            "verified": True,
            "pid": self.process.pid,
            "source": "harness-popen-handle",
            "command": list(cmd),
        }

        # Wait for server to start
        logging.info("Waiting for server to start...")
        max_retries = 30
        for _ in range(max_retries):
            try:
                resp = requests.get(f"{self.base_url}/dmcontrol", timeout=1)
                if resp.status_code == 200:
                    logging.info("Server is up.")
                    return
            except Exception:
                pass
            if self.process.poll() is not None:
                raise RuntimeError("Server process exited prematurely.")
            time.sleep(1)
        raise RuntimeError("Timed out waiting for server to start.")

    def stop(self):
        if self.process is not None:
            logging.info("Stopping local server...")
        self.cleanup_disposition = cleanup_owned_process(self.process, self.process_ownership)
        if self.cleanup_disposition["status"] == "refused-unverified-process-ownership":
            logging.error("Refusing cleanup because process ownership is not verified.")
        return self.cleanup_disposition

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Init Tracker Browser Smoke Harness")
    parser.add_argument("--list-scenarios", action="store_true", help="List all registered scenarios")
    parser.add_argument("--scenario", type=str, help="ID of the scenario to run")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help=f"Base URL of the server (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT, help=f"Root directory for artifacts (default: {DEFAULT_ARTIFACT_ROOT})")
    parser.add_argument("--start-server", action="store_true", help="Start a local server for the duration of the test")
    parser.add_argument("--headful", action="store_true", help="Run browser in headful mode")
    parser.add_argument("--max-rounds", type=int, default=2, help="Max rounds for multi-round scenarios (default: 2)")
    parser.add_argument("--max-turns", type=int, default=100, help="Max turns for multi-round scenarios (default: 100)")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="Slow down automation by this many ms per action (default: 0)")

    args = parser.parse_args()

    registry = Registry()
    registry.register(ScorcherIgniteGroundScenario())
    registry.register(BlackTanCombatExplorationScenario())
    registry.register(BlackTanThreeSurfaceWorkflowScenario())

    if args.list_scenarios:
        scenarios = registry.list_all()
        if not scenarios:
            print("No scenarios registered.")
        else:
            print("Available Scenarios:")
            for s in scenarios:
                print(f"  - {s.id}: {s.description}")
        return

    if not args.scenario:
        parser.print_help()
        sys.exit(0)

    scenario = registry.get(args.scenario)
    if not scenario:
        print(f"Error: Unknown scenario '{args.scenario}'", file=sys.stderr)
        sys.exit(1)

    collector = ArtifactCollector(args.artifact_root, scenario.id)
    server = ServerHandle(args.base_url, is_external=not args.start_server)

    success = False
    error_msg = None

    try:
        server.start(collector)

        with sync_playwright() as p:
            logging.info("Launching browser...")
            browser = p.chromium.launch(headless=not args.headful)

            role_pages: Dict[str, Page] = {}
            contexts: List[BrowserContext] = []

            for role in scenario.roles:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720}
                )
                contexts.append(context)
                page = context.new_page()
                role_pages[role.name] = page

                # Setup error collection
                page.on("pageerror", lambda err, r=role.name: logging.error(f"Page Error [{r}]: {err}"))
                page.on("console", lambda msg, r=role.name: logging.debug(f"Console [{r}]: {msg.text}") if msg.type != "error" else logging.error(f"Console Error [{r}]: {msg.text}"))

            config = {
                "max_rounds": args.max_rounds,
                "max_turns": args.max_turns,
                "slow_mo_ms": args.slow_mo_ms
            }

            try:
                run_result = scenario.run(args.base_url, role_pages, collector, config)
                if isinstance(run_result, tuple):
                    success, summary_ext = run_result
                else:
                    success = run_result
                    summary_ext = {}
            except Exception as e:
                logging.error(f"Scenario execution failed: {e}")
                error_msg = str(e)
                summary_ext = {}
                # Capture failure screenshot for all pages
                for role_name, page in role_pages.items():
                    collector.capture_screenshot(page, f"crash_{role_name}")
            finally:
                for context in contexts:
                    context.close()
                browser.close()

    except Exception as e:
        logging.error(f"Harness error: {e}")
        error_msg = str(e)
    finally:
        server.stop()

    # Write summary
    summary = {
        "scenario": scenario.id,
        "timestamp": collector.timestamp,
        "status": "pass" if success else "fail",
        "error": error_msg,
        "roles": [r.name for r in scenario.roles],
        "artifacts": {
            "server_stdout": str(server.stdout_path) if server.stdout_path else None,
            "server_stderr": str(server.stderr_path) if server.stderr_path else None,
            "screenshots": collector.screenshots,
        },
        **summary_ext
    }
    collector.write_summary(summary)
    logging.info(f"Artifact directory: {collector.run_dir}")

    if not success:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()

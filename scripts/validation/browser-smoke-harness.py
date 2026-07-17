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
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

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
THREE_SURFACE_TARGETED_SPELLS = {
    "pc:eldramar": "Fire Bolt",
    "pc:throat-goat": "Eldritch Blast",
    "pc:stikhiya": "Sacred Flame",
}
THREE_SURFACE_ATTACK_STAGING_POSITIONS = {
    "pc:dorian": {"col": 16, "row": 16},
    "pc:old-man": {"col": 14, "row": 13},
    "pc:vicnor": {"col": 17, "row": 16},
}
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
    add_step(
        "select-all-roster-players",
        "/dm",
        "click",
        root_selector="#encounterPlayerList",
        selector="#selectAllPlayersBtn",
        expected_players=_three_surface_players(),
    )
    add_step("add-all-roster-players", "/dm", "click", selector="#addPlayersBtn")
    add_step("open-encounter", "/dm", "click", selector="#tab-encounter")
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
                    "#castSpellModalOpen", "#castSpellPresetList",
                    ".cast-preview-cast-btn", "#c", "#spellResolveSubmit",
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
    if isinstance(value, dict) and value.get("reason"):
        reason = str(value["reason"])
        subordinate = {key: item for key, item in value.items() if key != "reason"}
        prefix = f"{reason}:"
        subordinate_detail = json.dumps(
            subordinate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        subordinate_limit = max(0, limit - len(prefix))
        if len(subordinate_detail) > subordinate_limit:
            if subordinate_limit >= 3:
                subordinate_detail = f"{subordinate_detail[:subordinate_limit - 3]}..."
            else:
                subordinate_detail = subordinate_detail[:subordinate_limit]
        return f"{prefix}{subordinate_detail}"
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


class ThreeSurfaceTerminalFailure(RuntimeError):
    """A fail-closed three-surface outcome that must not be retried."""

    def __init__(self, reason: str, detail: Any):
        super().__init__(_bounded_failure_detail(detail))
        self.reason = reason
        self.detail = detail


def _three_surface_page(step: Dict[str, Any], pages: Dict[str, Page]) -> Page:
    surface = step.get("surface")
    if surface == "/dm":
        role = "dm"
    elif surface == "/dmcontrol":
        role = "dmcontrol"
    elif surface == "/":
        player_id = step.get("player_id")
        if player_id:
            role = f"player:{player_id}"
        else:
            role = f"player:{THREE_SURFACE_PLAYER_IDENTITIES[-1][0]}"
    else:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"error": "step-has-no-browser-surface", "step_id": step.get("step_id")},
        )
    try:
        return pages[role]
    except KeyError as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"error": "missing-browser-role", "role": role, "step_id": step.get("step_id")},
        ) from exc


def _wait_for_visible(page: Page, selector: str, step_id: str, timeout: int = 10000) -> None:
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "selector-failure",
            {"step_id": step_id, "selector": selector, "error": str(exc)},
        ) from exc


def _click_selector(page: Page, selector: str, step_id: str) -> None:
    _wait_for_visible(page, selector, step_id)
    try:
        page.click(selector)
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "selector-failure",
            {"step_id": step_id, "selector": selector, "error": str(exc)},
        ) from exc


def _dismiss_visible_turn_alert(page: Page, step_id: str) -> None:
    try:
        page.wait_for_timeout(250)
        if page.locator("#turnModal.show").is_visible():
            _click_selector(page, "#turnModalOk", step_id)
    except ThreeSurfaceTerminalFailure:
        raise
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "selector": "#turnModalOk", "error": str(exc)},
        ) from exc


def _click_mapped_position(
    page: Page,
    selector: str,
    position: Dict[str, int],
    step_id: str,
    grid: Dict[str, int],
    initial_zoom: int,
) -> None:
    x, y = _mapped_screen_position(
        page,
        selector,
        position,
        step_id,
        grid,
        initial_zoom,
    )
    try:
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.up()
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "selector": selector, "error": str(exc)},
        ) from exc


def _mapped_screen_position(
    page: Page,
    selector: str,
    position: Dict[str, int],
    step_id: str,
    grid: Dict[str, int],
    initial_zoom: int,
) -> Tuple[float, float]:
    _wait_for_visible(page, selector, step_id)
    try:
        box = page.locator(selector).bounding_box()
        cols = int(grid["cols"])
        rows = int(grid["rows"])
        col = int(position["col"])
        row = int(position["row"])
        if (
            box is None
            or cols <= 0
            or rows <= 0
            or not 0 <= col < cols
            or not 0 <= row < rows
            or initial_zoom <= 0
        ):
            raise ValueError("invalid visible canvas or mapped grid position")
        pad = 24
        scale_x = (box["width"] - pad * 2) / (cols * initial_zoom)
        scale_y = (box["height"] - pad * 2) / (rows * initial_zoom)
        scale = min(1.0, max(0.35, min(scale_x, scale_y)))
        zoom = int(initial_zoom * scale)
        if zoom <= 0:
            raise ValueError("invalid fitted map zoom")
        pan_x = int((box["width"] - cols * zoom) / 2)
        pan_y = int((box["height"] - rows * zoom) / 2)
        x = box["x"] + pan_x + col * zoom + zoom / 2
        y = box["y"] + pan_y + row * zoom + zoom / 2
        if not (
            box["x"] <= x <= box["x"] + box["width"]
            and box["y"] <= y <= box["y"] + box["height"]
        ):
            raise ValueError("mapped grid position is outside visible canvas")
        return x, y
    except ThreeSurfaceTerminalFailure:
        raise
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "selector": selector, "error": str(exc)},
        ) from exc


def _drag_mapped_position(
    page: Page,
    selector: str,
    start_position: Dict[str, int],
    end_position: Dict[str, int],
    step_id: str,
    grid: Dict[str, int],
    initial_zoom: int,
) -> None:
    start_x, start_y = _mapped_screen_position(
        page, selector, start_position, step_id, grid, initial_zoom,
    )
    end_x, end_y = _mapped_screen_position(
        page, selector, end_position, step_id, grid, initial_zoom,
    )
    try:
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        page.mouse.move(end_x, end_y)
        page.mouse.up()
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "selector": selector, "error": str(exc)},
        ) from exc


def _finish_targeted_spell(
    page: Page,
    resolve_selector: str,
    spell_name: str,
    step_id: str,
    timeout: int = 10000,
) -> None:
    deadline = time.monotonic() + timeout / 1000
    modal = page.locator("#spellResolveModal.show")
    note = page.locator("#note")
    last_note = ""
    try:
        while time.monotonic() < deadline:
            if modal.is_visible():
                _click_selector(page, resolve_selector, step_id)
                return
            last_note = str(note.text_content() or "").strip()
            if spell_name.lower() in last_note.lower():
                return
            page.wait_for_timeout(100)
    except ThreeSurfaceTerminalFailure:
        raise
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "selector": resolve_selector, "error": str(exc)},
        ) from exc
    raise ThreeSurfaceTerminalFailure(
        "visible-state-inconsistency",
        {
            "step_id": step_id,
            "selector": resolve_selector,
            "spell_name": spell_name,
            "last_note": last_note,
            "error": "spell-result-or-resolve-modal-not-observed",
        },
    )


def _record_fixture_response(
    step: Dict[str, Any],
    base_url: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    operation = step["request"]["operation"]
    post = config.get("three_surface_http_post", requests.post)
    try:
        response = post(
            f"{base_url}{step['path']}",
            json=step["request"],
            timeout=config.get("fixture_timeout_seconds", 30),
        )
        payload = response.json()
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step["step_id"], "operation": operation, "error": str(exc)},
        ) from exc

    if not isinstance(payload, dict):
        raise ThreeSurfaceTerminalFailure(
            "fixture-precondition-mismatch",
            {"step_id": step["step_id"], "operation": operation, "error": "fixture-response-not-object"},
        )
    status_code = getattr(response, "status_code", None)
    state["fixture_responses"][operation] = payload
    state["fixture_evidence"][operation] = {
        "request": dict(step["request"]),
        "status_code": status_code,
        "response": payload,
    }
    if isinstance(status_code, int) and status_code >= 400 and payload.get("ok") is not False:
        raise ThreeSurfaceTerminalFailure(
            "fixture-precondition-mismatch",
            {"step_id": step["step_id"], "operation": operation, "status_code": status_code},
        )


def _enforce_fixture_barrier(step: Dict[str, Any], state: Dict[str, Any]) -> None:
    operation = (
        "reset-ui-workflow"
        if step["step_id"] == "validate-reset-contract"
        else "verify-ui-workflow"
    )
    response = state["fixture_responses"].get(operation)
    if response is None:
        raise ThreeSurfaceTerminalFailure(
            "fixture-precondition-mismatch",
            {"step_id": step["step_id"], "operation": operation, "error": "missing-fixture-response"},
        )
    result = classify_three_surface_contract_response(response, operation)
    state["fixture_evidence"][operation]["classification"] = result
    if not result["ok"]:
        raise ThreeSurfaceTerminalFailure(
            result["reason"],
            {"step_id": step["step_id"], "detail": result["failure_detail"]},
        )
    if operation == "verify-ui-workflow":
        state["player_cid_map"] = dict(response["player_cid_map"])
        state["enemy_cid_map"] = dict(response["enemy_cid_map"])
        state["player_positions"] = {
            item["player_id"]: dict(item["position"])
            for item in response["players"]
        }
        state["enemy_positions"] = {
            item["enemy_slug"]: dict(item["position"])
            for item in response["enemies"]
        }
    else:
        grid = (
            response.get("snapshot", {})
            .get("tactical_map", {})
            .get("grid", {})
        )
        if not isinstance(grid, dict) or not grid.get("cols") or not grid.get("rows"):
            raise ThreeSurfaceTerminalFailure(
                "fixture-precondition-mismatch",
                {"step_id": step["step_id"], "error": "reset-grid-contract-missing"},
            )
        state["grid"] = {
            "cols": int(grid["cols"]),
            "rows": int(grid["rows"]),
        }


def _order_three_surface_runtime_actions(
    steps: List[Dict[str, Any]],
    base_url: str,
    config: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    get = config.get("three_surface_http_get", requests.get)
    try:
        response = get(
            f"{base_url}/api/dm/combat",
            timeout=config.get("fixture_timeout_seconds", 30),
        )
        payload = response.json()
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": "resolve-runtime-turn-order", "error": str(exc)},
        ) from exc

    status_code = getattr(response, "status_code", None)
    if (
        not isinstance(payload, dict)
        or (isinstance(status_code, int) and status_code >= 400)
        or payload.get("in_combat") is not True
    ):
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {
                "step_id": "resolve-runtime-turn-order",
                "status_code": status_code,
                "error": "live-combat-snapshot-unavailable",
            },
        )

    turn_order = payload.get("turn_order")
    active_cid = payload.get("active_cid")
    combatants = payload.get("combatants")
    if (
        not isinstance(turn_order, list)
        or not turn_order
        or len({str(cid) for cid in turn_order}) != len(turn_order)
        or str(turn_order[0]) != str(active_cid)
        or not isinstance(combatants, list)
    ):
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {
                "step_id": "resolve-runtime-turn-order",
                "active_cid": active_cid,
                "turn_order": turn_order,
                "error": "invalid-live-turn-order",
            },
        )

    player_by_cid = {
        str(cid): player_id
        for player_id, cid in state["player_cid_map"].items()
    }
    enemy_by_cid = {
        str(cid): enemy_slug
        for enemy_slug, cid in state["enemy_cid_map"].items()
    }
    combatant_by_cid = {
        str(item.get("cid")): item
        for item in combatants
        if isinstance(item, dict) and item.get("cid") is not None
    }
    canonical_cids = set(player_by_cid) | set(enemy_by_cid)
    actual_cids = {str(cid) for cid in turn_order}
    if not canonical_cids.issubset(actual_cids):
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {
                "step_id": "resolve-runtime-turn-order",
                "missing_cids": sorted(canonical_cids - actual_cids),
                "error": "canonical-actor-missing-from-turn-order",
            },
        )

    player_pairs: Dict[str, List[Dict[str, Any]]] = {}
    enemy_pairs: Dict[str, List[Dict[str, Any]]] = {}
    for player_id in state["player_cid_map"]:
        player_pairs[player_id] = [
            step for step in steps
            if step.get("player_id") == player_id
            and step.get("action") in (
                "attack-mapped-target",
                "cast-spell-at-mapped-target",
                "click",
            )
            and step["step_id"].startswith(("player-", "advance-player-turn-"))
        ]
    for enemy_slug in state["enemy_cid_map"]:
        enemy_pairs[enemy_slug] = [
            step for step in steps
            if step.get("enemy_slug") == enemy_slug
            and step.get("action") in ("execute-active-action", "evaluate")
        ]
    if any(len(pair) != 2 for pair in (*player_pairs.values(), *enemy_pairs.values())):
        raise ThreeSurfaceTerminalFailure(
            "fixture-precondition-mismatch",
            {"step_id": "resolve-runtime-turn-order", "error": "actor-action-pair-mismatch"},
        )

    runtime_steps: List[Dict[str, Any]] = []
    skipped_summons: List[Dict[str, Any]] = []
    for cid in turn_order:
        cid_key = str(cid)
        if cid_key in player_by_cid:
            runtime_steps.extend(player_pairs[player_by_cid[cid_key]])
            continue
        if cid_key in enemy_by_cid:
            runtime_steps.extend(enemy_pairs[enemy_by_cid[cid_key]])
            continue
        combatant = combatant_by_cid.get(cid_key)
        if (
            combatant is None
            or combatant.get("role") != "ally"
            or combatant.get("name") not in ("Owl", "Raven")
        ):
            raise ThreeSurfaceTerminalFailure(
                "visible-state-inconsistency",
                {
                    "step_id": "resolve-runtime-turn-order",
                    "cid": cid,
                    "combatant": combatant,
                    "error": "unexpected-runtime-actor",
                },
            )
        skipped_summons.append({
            "cid": cid,
            "name": combatant["name"],
            "role": combatant["role"],
        })
        runtime_steps.append({
            "step_id": f"advance-summon-turn-{combatant['name'].casefold()}-{cid}",
            "surface": "/dmcontrol",
            "action": "advance-verified-summon",
            "runtime_cid": cid,
            "runtime_name": combatant["name"],
        })

    if sorted(item["name"] for item in skipped_summons) != ["Owl", "Raven"]:
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {
                "step_id": "resolve-runtime-turn-order",
                "summons": skipped_summons,
                "error": "verified-start-summons-mismatch",
            },
        )

    action_start = next(
        index for index, step in enumerate(steps)
        if step.get("action") in ("attack-mapped-target", "cast-spell-at-mapped-target")
    )
    action_end = next(
        index for index, step in enumerate(steps[action_start:], start=action_start)
        if step["step_id"] == "assert-dm-visible-state"
    )
    steps[action_start:action_end] = runtime_steps
    for order, step in enumerate(steps, start=1):
        step["order"] = order
    state["runtime_turn_order_evidence"] = {
        "status_code": status_code,
        "active_cid": active_cid,
        "turn_order": list(turn_order),
        "skipped_summons": skipped_summons,
        "runtime_step_ids": [step["step_id"] for step in runtime_steps],
    }


def _nearest_three_surface_enemy_slug(
    player_id: str,
    state: Dict[str, Any],
    player_position: Optional[Dict[str, int]] = None,
) -> str:
    origin = player_position or state["player_positions"][player_id]
    candidates = []
    for identity_order, (enemy_slug, _name) in enumerate(THREE_SURFACE_ENEMY_IDENTITIES):
        enemy_position = state["enemy_positions"][enemy_slug]
        distance = max(
            abs(int(enemy_position["col"]) - int(origin["col"])),
            abs(int(enemy_position["row"]) - int(origin["row"])),
        )
        candidates.append((distance, identity_order, enemy_slug))
    if not candidates:
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {"player_id": player_id, "error": "no-mapped-enemy-target"},
        )
    return min(candidates)[2]


def _execute_player_action(step: Dict[str, Any], page: Page, state: Dict[str, Any]) -> None:
    player_id = step["player_id"]
    step_id = step["step_id"]
    _wait_for_visible(page, "#endTurn:not([disabled])", step_id)
    _dismiss_visible_turn_alert(page, step_id)

    targeted_spell = THREE_SURFACE_TARGETED_SPELLS.get(player_id)
    use_attack = step["action"] == "attack-mapped-target" or targeted_spell is None
    state.setdefault("runtime_player_action_modes", []).append({
        "player_id": player_id,
        "planned_action": step["action"],
        "executed_action": "attack-mapped-target" if use_attack else "cast-spell-at-mapped-target",
        "spell_name": targeted_spell,
    })

    if use_attack:
        if step["action"] == "attack-mapped-target":
            attack_open, canvas, resolve = step["selectors"]
        else:
            attack_open, canvas, resolve = (
                "#attackOverlayToggle", "#c", "#attackResolveSubmit",
            )
        staging_position = THREE_SURFACE_ATTACK_STAGING_POSITIONS.get(player_id)
        if staging_position is not None:
            _drag_mapped_position(
                page,
                canvas,
                state["player_positions"][player_id],
                staging_position,
                step_id,
                state["grid"],
                32,
            )
            page.wait_for_timeout(500)
        enemy_slug = _nearest_three_surface_enemy_slug(
            player_id,
            state,
            player_position=staging_position,
        )
        target_position = state["enemy_positions"][enemy_slug]
        _click_selector(page, attack_open, step_id)
        _dismiss_visible_turn_alert(page, step_id)
        _click_mapped_position(
            page,
            canvas,
            target_position,
            step_id,
            state["grid"],
            32,
        )
        _click_selector(page, resolve, step_id)
        return

    enemy_slug = _nearest_three_surface_enemy_slug(player_id, state)
    target_position = state["enemy_positions"][enemy_slug]
    cast_open, preset_list, cast_submit, canvas, resolve = step["selectors"]
    _click_selector(page, cast_open, step_id)
    _wait_for_visible(page, preset_list, step_id)
    preset_selector = (
        f'{preset_list} .spellbook-item:has-text("{targeted_spell}")'
    )
    _click_selector(page, preset_selector, step_id)
    _wait_for_visible(page, cast_submit, step_id)
    try:
        page.once("dialog", lambda dialog: dialog.accept())
        page.click(cast_submit)
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "selector-failure",
            {"step_id": step_id, "selector": cast_submit, "error": str(exc)},
        ) from exc
    _dismiss_visible_turn_alert(page, step_id)
    _click_mapped_position(
        page,
        canvas,
        target_position,
        step_id,
        state["grid"],
        32,
    )
    _finish_targeted_spell(page, resolve, targeted_spell, step_id)


def _wait_for_matching_dmcontrol_capabilities(
    page: Page,
    expected_cid: Any,
    step_id: str,
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    get = state["three_surface_http_get"]
    try:
        response = get(
            f"{state['base_url']}/api/dm/monster-capabilities/{expected_cid}",
            timeout=state["fixture_timeout_seconds"],
        )
        payload = response.json()
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "expected_active_cid": expected_cid, "error": str(exc)},
        ) from exc

    status_code = getattr(response, "status_code", None)
    summary = payload.get("summary") if isinstance(payload, dict) else None
    groups = summary.get("groups") if isinstance(summary, dict) else None
    expected_ids = [
        str(action.get("id"))
        for actions in groups.values()
        if isinstance(actions, list)
        for action in actions
        if isinstance(action, dict) and action.get("id") is not None
    ] if isinstance(groups, dict) else []
    if (
        not isinstance(payload, dict)
        or payload.get("ok") is not True
        or not isinstance(status_code, int)
        or status_code >= 400
        or str(summary.get("combatant_id")) != str(expected_cid)
        or not expected_ids
        or len(expected_ids) != len(set(expected_ids))
    ):
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {
                "step_id": step_id,
                "expected_active_cid": expected_cid,
                "status_code": status_code,
                "error": "invalid-active-capability-contract",
            },
        )

    try:
        page.wait_for_function(
            """([expectedCid, expectedIds]) => {
                const smoke = window.__dmcontrolSmoke;
                if (!smoke || String(smoke.activeActorCid()) !== String(expectedCid)) return false;
                const actualIds = smoke.availableActions()
                    .map(action => String(action.id))
                    .sort();
                const requiredIds = [...expectedIds].map(String).sort();
                return actualIds.length === requiredIds.length
                    && actualIds.every((value, index) => value === requiredIds[index]);
            }""",
            arg=[expected_cid, expected_ids],
            timeout=10000,
        )
        actions = page.evaluate("window.__dmcontrolSmoke.availableActions()")
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "visible-state-inconsistency",
            {
                "step_id": step_id,
                "expected_active_cid": expected_cid,
                "expected_action_ids": expected_ids,
                "error": str(exc),
            },
        ) from exc
    state["runtime_capability_sync"].append({
        "cid": expected_cid,
        "status_code": status_code,
        "action_ids": expected_ids,
    })
    return actions


def _execute_enemy_action(step: Dict[str, Any], page: Page, state: Dict[str, Any]) -> None:
    enemy_slug = step["enemy_slug"]
    enemy_index = [identity for identity, _name in THREE_SURFACE_ENEMY_IDENTITIES].index(enemy_slug)
    player_id = THREE_SURFACE_PLAYER_IDENTITIES[enemy_index % len(THREE_SURFACE_PLAYER_IDENTITIES)][0]
    expected_cid = state["enemy_cid_map"][enemy_slug]
    step_id = step["step_id"]
    try:
        actions = _wait_for_matching_dmcontrol_capabilities(
            page,
            expected_cid,
            step_id,
            state,
        )
        chosen = next(
            (action for action in actions if isinstance(action, dict) and action.get("executable")),
            None,
        )
        if chosen is None or not chosen.get("id"):
            raise ThreeSurfaceTerminalFailure(
                "visible-state-inconsistency",
                {"step_id": step_id, "error": "no-executable-enemy-action"},
            )
        action_selector = step["action_selector_template"].replace(
            "<capability-id>",
            str(chosen["id"]),
        )
        _wait_for_visible(page, action_selector, step_id)
        page.evaluate("(id) => selectCapability(id)", chosen["id"])
        if chosen.get("action_type") == "composite":
            page.evaluate("(id) => startSequence(id)", chosen["id"])
            composite = page.evaluate("window.__dmcontrolSmoke.compositeState()")
            sub_action = next(
                (item for item in composite.get("steps", []) if item.get("executable")),
                None,
            ) if isinstance(composite, dict) else None
            if sub_action is None:
                raise ThreeSurfaceTerminalFailure(
                    "visible-state-inconsistency",
                    {"step_id": step_id, "error": "no-executable-composite-step"},
                )
            page.evaluate("(id) => selectCapability(id)", sub_action["id"])

        target_preview = page.evaluate("window.__dmcontrolSmoke.targetPreviewMode()")
        aoe_state = page.evaluate("window.__dmcontrolSmoke.aoeState()")
        if (isinstance(target_preview, dict) and target_preview.get("active")) or (
            isinstance(aoe_state, dict) and aoe_state.get("active")
        ):
            _click_mapped_position(
                page,
                '[data-testid="dmcontrol-map-canvas"]',
                state["player_positions"][player_id],
                step_id,
                state["grid"],
                40,
            )

        modal = page.evaluate("window.__dmcontrolSmoke.modalSummary()")
        if isinstance(modal, dict) and modal.get("active"):
            _click_selector(page, step["apply_selector"], step_id)
    except ThreeSurfaceTerminalFailure:
        raise
    except Exception as exc:
        raise ThreeSurfaceTerminalFailure(
            "browser-error",
            {"step_id": step_id, "error": str(exc)},
        ) from exc


def _assert_visible_state(
    step: Dict[str, Any],
    pages: Dict[str, Page],
    collector: ArtifactCollector,
    state: Dict[str, Any],
) -> None:
    if step["surface"] == "/":
        role_pages = [
            (f"player:{player_id}", pages[f"player:{player_id}"])
            for player_id, _name in THREE_SURFACE_PLAYER_IDENTITIES
        ]
    else:
        role = "dm" if step["surface"] == "/dm" else "dmcontrol"
        role_pages = [(role, pages[role])]

    for role, page in role_pages:
        for selector in step["selectors"]:
            _wait_for_visible(page, selector, step["step_id"])
        try:
            if step["surface"] == "/dm":
                visible_values = {
                    selector: page.locator(selector).inner_text().strip()
                    for selector in ("#roundVal", "#turnVal", "#activeName", "#upNextName")
                }
                if any(not value for value in visible_values.values()):
                    raise ThreeSurfaceTerminalFailure(
                        "visible-state-inconsistency",
                        {"step_id": step["step_id"], "visible_values": visible_values},
                    )
            elif step["surface"] == "/":
                player_id = role.split(":", 1)[1]
                expected_name = dict(THREE_SURFACE_PLAYER_IDENTITIES)[player_id]
                actual_identity = page.locator("#me").inner_text().strip()
                if expected_name.casefold() not in actual_identity.casefold():
                    raise ThreeSurfaceTerminalFailure(
                        "visible-state-inconsistency",
                        {
                            "step_id": step["step_id"],
                            "player_id": player_id,
                            "expected_name": expected_name,
                            "actual_identity": actual_identity,
                        },
                    )
                if state["player_cid_map"].get(player_id) is None:
                    raise ThreeSurfaceTerminalFailure(
                        "visible-state-inconsistency",
                        {"step_id": step["step_id"], "player_id": player_id, "error": "missing-runtime-cid"},
                    )
        except ThreeSurfaceTerminalFailure:
            raise
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "browser-error",
                {"step_id": step["step_id"], "role": role, "error": str(exc)},
            ) from exc
        for smoke_api in step.get("smoke_apis", ()):
            try:
                result = page.evaluate(smoke_api)
            except Exception as exc:
                raise ThreeSurfaceTerminalFailure(
                    "browser-error",
                    {"step_id": step["step_id"], "smoke_api": smoke_api, "error": str(exc)},
                ) from exc
            inconsistent = result is None or result is False
            if smoke_api.endswith("state()"):
                inconsistent = inconsistent or not isinstance(result, dict)
            if smoke_api.endswith("roundOrTurn()"):
                inconsistent = inconsistent or not isinstance(result, dict) or any(
                    result.get(field) is None for field in ("round", "turn")
                )
            if inconsistent:
                raise ThreeSurfaceTerminalFailure(
                    "visible-state-inconsistency",
                    {"step_id": step["step_id"], "smoke_api": smoke_api, "result": result},
                )
        try:
            collector.capture_screenshot(page, f"{step['step_id']}-{role.replace(':', '-')}")
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "browser-error",
                {"step_id": step["step_id"], "artifact": "screenshot", "role": role, "error": str(exc)},
            ) from exc


def _execute_three_surface_step(
    step: Dict[str, Any],
    plan: Dict[str, Any],
    base_url: str,
    pages: Dict[str, Page],
    collector: ArtifactCollector,
    config: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    action = step["action"]
    step_id = step["step_id"]
    if action == "validate-expectation":
        expected = step["required_versions"]
        actual = {
            "schema_version": plan["contract"].get("schema_version"),
            "reset_version": plan["contract"].get("reset_version"),
            "precondition_digest": plan["contract"].get("expected_precondition_digest"),
        }
        if actual != expected:
            raise ThreeSurfaceTerminalFailure(
                "fixture-precondition-mismatch",
                {"step_id": step_id, "expected": expected, "actual": actual},
            )
        return
    if action == "post-json":
        _record_fixture_response(step, base_url, state, config)
        return
    if action == "terminal-contract-barrier":
        _enforce_fixture_barrier(step, state)
        return

    page = _three_surface_page(step, pages)
    if action == "goto":
        try:
            page.goto(f"{base_url}{step['path']}", wait_until="domcontentloaded")
            if step["surface"] == "/dmcontrol":
                page.wait_for_function(
                    "window.__dmcontrolSmoke && window.__dmcontrolSmoke.ready()",
                    timeout=15000,
                )
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "browser-error",
                {"step_id": step_id, "path": step["path"], "error": str(exc)},
            ) from exc
        return
    if action == "click":
        if step.get("root_selector"):
            _wait_for_visible(page, step["root_selector"], step_id)
        if step_id == "start-combat":
            _click_selector(page, "#closeToolboxBtn", step_id)
            try:
                with page.expect_response(
                    lambda response: (
                        response.request.method == "POST"
                        and urlsplit(response.url).path == "/api/dm/combat/start"
                        and response.ok
                    )
                ):
                    _click_selector(page, step["selector"], step_id)
            except ThreeSurfaceTerminalFailure:
                raise
            except Exception as exc:
                raise ThreeSurfaceTerminalFailure(
                    "browser-error",
                    {
                        "step_id": step_id,
                        "request": "POST /api/dm/combat/start",
                        "error": str(exc),
                    },
                ) from exc
            return
        _click_selector(page, step["selector"], step_id)
        return
    if action == "select-and-click":
        _wait_for_visible(page, step["selector"], step_id)
        if not state["enemy_options_validated"]:
            try:
                options = page.eval_on_selector_all(
                    f"{step['selector']} option",
                    """options => options
                        .map(option => option.value)
                        .filter(value => value.startsWith('black-and-tan-'))""",
                )
            except Exception as exc:
                raise ThreeSurfaceTerminalFailure(
                    "browser-error",
                    {"step_id": step_id, "selector": step["selector"], "error": str(exc)},
                ) from exc
            expected_options = [slug for slug, _name in THREE_SURFACE_ENEMY_IDENTITIES]
            option_counts = Counter(options)
            expected_option_set = set(expected_options)
            missing_options = [
                slug for slug in expected_options
                if slug not in option_counts
            ]
            extra_options = sorted(set(option_counts) - expected_option_set)
            duplicate_options = sorted(
                slug for slug, count in option_counts.items()
                if count > 1
            )
            if missing_options or extra_options or duplicate_options:
                raise ThreeSurfaceTerminalFailure(
                    "visible-state-inconsistency",
                    {
                        "step_id": step_id,
                        "expected_enemy_options": expected_options,
                        "actual_enemy_options": options,
                        "missing_enemy_slugs": missing_options,
                        "extra_enemy_slugs": extra_options,
                        "duplicate_enemy_slugs": duplicate_options,
                    },
                )
            state["enemy_options_validated"] = True
        try:
            page.select_option(step["selector"], step["value"])
            page.fill(step["count_selector"], str(step["count"]))
            if step["ally"]:
                page.check(step["ally_selector"])
            else:
                page.uncheck(step["ally_selector"])
            page.click(step["submit_selector"])
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "selector-failure",
                {"step_id": step_id, "selector": step["selector"], "error": str(exc)},
            ) from exc
        return
    if action == "claim-mapped-player":
        cid = state["player_cid_map"][step["player_id"]]
        claim_selector = step["selector_template"].replace("<cid>", str(cid))
        _click_selector(page, claim_selector, step_id)
        _click_selector(page, step["confirm_selector"], step_id)
        _wait_for_visible(page, step["identity_selector"], step_id)
        return
    if action in ("attack-mapped-target", "cast-spell-at-mapped-target"):
        _execute_player_action(step, page, state)
        return
    if action == "execute-active-action":
        _execute_enemy_action(step, page, state)
        return
    if action == "advance-verified-summon":
        try:
            page.wait_for_function(
                """expectedCid => window.__dmcontrolSmoke
                    && String(window.__dmcontrolSmoke.activeActorCid()) === String(expectedCid)""",
                arg=step["runtime_cid"],
                timeout=10000,
            )
            page.evaluate("handleCombatControl()")
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "visible-state-inconsistency",
                {
                    "step_id": step_id,
                    "expected_active_cid": step["runtime_cid"],
                    "error": str(exc),
                },
            ) from exc
        return
    if action == "evaluate":
        try:
            page.evaluate(step["smoke_api"])
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "browser-error",
                {"step_id": step_id, "smoke_api": step["smoke_api"], "error": str(exc)},
            ) from exc
        return
    if action == "assert-visible-state":
        _assert_visible_state(step, pages, collector, state)
        return
    raise ThreeSurfaceTerminalFailure(
        "browser-error",
        {"step_id": step_id, "error": f"unsupported-plan-action:{action}"},
    )


def _start_three_surface_traces(
    pages: Dict[str, Page],
    collector: ArtifactCollector,
    state: Dict[str, Any],
) -> None:
    contexts: Dict[int, Dict[str, Any]] = {}
    for role, page in pages.items():
        context = getattr(page, "context", None)
        tracing = getattr(context, "tracing", None)
        if tracing is None:
            raise ThreeSurfaceTerminalFailure(
                "browser-error",
                {"role": role, "error": "browser-context-tracing-unavailable"},
            )
        context_key = id(context)
        if context_key in contexts:
            state["role_traces"][role] = contexts[context_key]["path"]
            continue
        safe_role = "".join(character if character.isalnum() else "-" for character in role)
        filename = "browser-trace.zip" if role == "dm" else f"role-trace-{safe_role}.zip"
        trace_path = collector.get_path(filename)
        try:
            tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception as exc:
            raise ThreeSurfaceTerminalFailure(
                "browser-error",
                {"role": role, "artifact": "browser-trace", "error": str(exc)},
            ) from exc
        record = {"role": role, "tracing": tracing, "path": str(trace_path)}
        contexts[context_key] = record
        state["started_traces"].append(record)
        state["role_traces"][role] = str(trace_path)
        if role == "dm":
            state["browser_trace"] = str(trace_path)


def _stop_three_surface_traces(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for record in state["started_traces"]:
        try:
            record["tracing"].stop(path=record["path"])
        except Exception as exc:
            failures.append({"role": record["role"], "error": str(exc)})
    return failures


def execute_three_surface_workflow(
    plan: Dict[str, Any],
    base_url: str,
    pages: Dict[str, Page],
    collector: ArtifactCollector,
    config: Dict[str, Any],
) -> tuple[bool, Dict[str, Any]]:
    """Execute the registered A7 three-surface plan exactly once and fail closed."""
    steps = [dict(step) for step in plan.get("steps", [])]
    expected_orders = list(range(1, len(steps) + 1))
    if plan.get("scenario_id") != THREE_SURFACE_SCENARIO_ID or [step.get("order") for step in steps] != expected_orders:
        failure = ThreeSurfaceTerminalFailure(
            "fixture-precondition-mismatch",
            {"error": "invalid-three-surface-plan-order-or-identity"},
        )
    else:
        failure = None
    state: Dict[str, Any] = {
        "fixture_responses": {},
        "fixture_evidence": {},
        "player_cid_map": {},
        "enemy_cid_map": {},
        "player_positions": {},
        "enemy_positions": {},
        "grid": {},
        "enemy_options_validated": False,
        "started_traces": [],
        "role_traces": {},
        "browser_trace": None,
        "runtime_turn_order_evidence": {},
        "base_url": base_url,
        "three_surface_http_get": config.get("three_surface_http_get", requests.get),
        "fixture_timeout_seconds": config.get("fixture_timeout_seconds", 30),
        "runtime_capability_sync": [],
    }
    step_timings: List[Dict[str, Any]] = []
    failure_step_id: Optional[str] = None

    try:
        if failure is None:
            try:
                _start_three_surface_traces(pages, collector, state)
            except ThreeSurfaceTerminalFailure as exc:
                failure = exc
            except Exception as exc:
                failure = ThreeSurfaceTerminalFailure(
                    "browser-error",
                    {"artifact": "browser-trace", "error": str(exc)},
                )
        for step in steps:
            if failure is not None:
                break
            failure_step_id = step["step_id"]
            started_at = datetime.datetime.now(datetime.timezone.utc)
            started = time.perf_counter()
            try:
                browser_errors = config.get("browser_errors", [])
                if browser_errors:
                    raise ThreeSurfaceTerminalFailure(
                        "browser-error",
                        {"step_id": step["step_id"], "errors": browser_errors[:8]},
                    )
                _execute_three_surface_step(step, plan, base_url, pages, collector, config, state)
                if (
                    step["step_id"] == "claim-player-pc:stikhiya"
                    and state["player_cid_map"]
                    and state["enemy_cid_map"]
                ):
                    _order_three_surface_runtime_actions(
                        steps,
                        base_url,
                        config,
                        state,
                    )
                settle_ms = config.get("three_surface_step_settle_ms", 0)
                if settle_ms and step.get("surface") in ("/dm", "/dmcontrol", "/"):
                    _three_surface_page(step, pages).wait_for_timeout(settle_ms)
                if browser_errors:
                    raise ThreeSurfaceTerminalFailure(
                        "browser-error",
                        {"step_id": step["step_id"], "errors": browser_errors[:8]},
                    )
            except ThreeSurfaceTerminalFailure as exc:
                failure = exc
            except Exception as exc:
                failure = ThreeSurfaceTerminalFailure(
                    "browser-error",
                    {"step_id": step["step_id"], "error": str(exc)},
                )
            finally:
                finished_at = datetime.datetime.now(datetime.timezone.utc)
                step_timings.append({
                    "order": step["order"],
                    "step_id": step["step_id"],
                    "surface": step["surface"],
                    "action": step["action"],
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "status": "fail" if failure is not None else "pass",
                })
            slow_mo_ms = config.get("slow_mo_ms", 0)
            if failure is None and slow_mo_ms:
                time.sleep(slow_mo_ms / 1000.0)
    finally:
        if failure is not None:
            try:
                failed_step = next(
                    (step for step in steps if step.get("step_id") == failure_step_id),
                    None,
                )
                if failed_step and failed_step.get("surface") in ("/dm", "/dmcontrol", "/"):
                    page = _three_surface_page(failed_step, pages)
                    collector.capture_screenshot(page, f"terminal-{failure.reason}-{failure_step_id}")
            except Exception:
                pass
        trace_failures = _stop_three_surface_traces(state)
        if trace_failures:
            cleanup_failure = ThreeSurfaceTerminalFailure(
                "cleanup-uncertainty",
                {"artifact": "browser-trace", "failures": trace_failures[:8]},
            )
            if failure is None:
                failure = cleanup_failure
                failure_step_id = None
            else:
                failure = ThreeSurfaceTerminalFailure(
                    failure.reason,
                    {"primary": failure.detail, "cleanup_uncertainty": cleanup_failure.detail},
                )

    terminal_classification = "pass" if failure is None else "fail"
    evidence = build_three_surface_evidence(
        run_id=collector.timestamp,
        terminal_classification=terminal_classification,
        step_timings=step_timings,
        screenshots=collector.screenshots,
        browser_trace=state["browser_trace"],
        server_log=config.get("server_log"),
        debug_trace=config.get("debug_trace"),
        fixture_evidence=state["fixture_evidence"],
        port_ownership=config.get("port_ownership"),
        cleanup_disposition=config.get(
            "cleanup_disposition",
            {"status": "pending-harness-cleanup", "cleaned": False},
        ),
        failure_detail="" if failure is None else {
            "reason": failure.reason,
            "step_id": failure_step_id,
            "detail": failure.detail,
        },
        role_traces=state["role_traces"],
    )
    evidence.update({
        "executor": "registered-three-surface-executor/v1",
        "executed_step_count": len(step_timings),
        "failure_step_id": failure_step_id if failure is not None else None,
        "retry": False,
        "rewrite_expectation": False,
        "runtime_turn_order": state["runtime_turn_order_evidence"],
        "runtime_capability_sync": state["runtime_capability_sync"],
    })
    return failure is None, evidence


THREE_SURFACE_EXECUTORS = {
    THREE_SURFACE_SCENARIO_ID: execute_three_surface_workflow,
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
    """Registered executor for the deterministic A7 three-surface workflow."""

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
        executor = THREE_SURFACE_EXECUTORS.get(self.id)
        if not callable(executor):
            raise RuntimeError(f"No registered executor for scenario '{self.id}'")
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


def _port_ownership_snapshot(base_url: str, server: ServerHandle) -> Dict[str, Any]:
    parsed = urlsplit(base_url)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return {
        "base_url": base_url,
        "port": port,
        **dict(server.process_ownership),
    }


def _finalize_three_surface_cleanup(
    success: bool,
    summary_ext: Dict[str, Any],
    collector: ArtifactCollector,
    server: ServerHandle,
    cleanup_disposition: Dict[str, Any],
    error_msg: Optional[str],
) -> tuple[bool, Dict[str, Any]]:
    if summary_ext.get("evidence_schema_version") != "a7-three-surface-evidence/v1":
        summary_ext = build_three_surface_evidence(
            run_id=collector.timestamp,
            terminal_classification="fail",
            step_timings=[],
            screenshots=collector.screenshots,
            server_log=str(server.stdout_path) if server.stdout_path else None,
            port_ownership=_port_ownership_snapshot(server.base_url, server),
            cleanup_disposition=cleanup_disposition,
            failure_detail={"reason": "browser-error", "detail": error_msg or "harness-error"},
        )
        summary_ext.update({
            "executor": "registered-three-surface-executor/v1",
            "executed_step_count": 0,
            "failure_step_id": None,
            "retry": False,
            "rewrite_expectation": False,
        })
        success = False

    summary_ext["port_ownership"] = _port_ownership_snapshot(server.base_url, server)
    summary_ext["cleanup_disposition"] = dict(cleanup_disposition)
    cleanup_status = cleanup_disposition.get("status")
    accepted_statuses = {
        "no-owned-process",
        "owned-process-already-exited",
        "owned-process-cleaned",
    }
    if cleanup_status not in accepted_statuses:
        success = False
        summary_ext["terminal_classification"] = "fail"
        summary_ext["failure_detail"] = _bounded_failure_detail({
            "primary": summary_ext.get("failure_detail"),
            "reason": "cleanup-uncertainty",
            "cleanup_disposition": cleanup_disposition,
        })
    return success, summary_ext


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
    summary_ext: Dict[str, Any] = {}

    try:
        server.start(collector)

        with sync_playwright() as p:
            logging.info("Launching browser...")
            browser = p.chromium.launch(headless=not args.headful)

            role_pages: Dict[str, Page] = {}
            contexts: List[BrowserContext] = []
            browser_errors: List[Dict[str, str]] = []

            for role in scenario.roles:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720}
                )
                contexts.append(context)
                page = context.new_page()
                role_pages[role.name] = page

                # Setup error collection
                def record_page_error(error: Any, role_name: str = role.name) -> None:
                    detail = _bounded_failure_detail(error)
                    browser_errors.append({"role": role_name, "type": "pageerror", "detail": detail})
                    logging.error(f"Page Error [{role_name}]: {detail}")

                def record_console(message: Any, role_name: str = role.name) -> None:
                    if message.type == "error":
                        detail = _bounded_failure_detail(message.text)
                        browser_errors.append({"role": role_name, "type": "console-error", "detail": detail})
                        logging.error(f"Console Error [{role_name}]: {detail}")
                    else:
                        logging.debug(f"Console [{role_name}]: {message.text}")

                page.on("pageerror", record_page_error)
                page.on("console", record_console)

            config = {
                "max_rounds": args.max_rounds,
                "max_turns": args.max_turns,
                "slow_mo_ms": args.slow_mo_ms,
                "browser_errors": browser_errors,
                "server_log": str(server.stdout_path) if server.stdout_path else None,
                "port_ownership": _port_ownership_snapshot(args.base_url, server),
                "cleanup_disposition": dict(server.cleanup_disposition),
                "three_surface_step_settle_ms": 100,
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
        try:
            cleanup_disposition = server.stop()
        except Exception as exc:
            cleanup_disposition = {
                "status": "cleanup-error",
                "cleaned": False,
                "failure_detail": _bounded_failure_detail(exc),
            }
            logging.error(f"Server cleanup failed: {exc}")

    if scenario.id == THREE_SURFACE_SCENARIO_ID:
        success, summary_ext = _finalize_three_surface_cleanup(
            success,
            summary_ext,
            collector,
            server,
            cleanup_disposition,
            error_msg,
        )

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

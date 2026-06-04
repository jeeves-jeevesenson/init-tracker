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

    def run(self, base_url: str, pages: Dict[str, Page], collector: ArtifactCollector) -> bool:
        """Runs the scenario. To be implemented by subclasses in Gate 4+."""
        raise NotImplementedError(f"Scenario '{self.id}' not implemented")

class ScorcherIgniteGroundScenario(Scenario):
    """
    Scenario for Black and Tan VDA Scorcher Ignite Ground pilot.
    """
    def __init__(self):
        super().__init__("scorcher-ignite-ground", "Black and Tan VDA Scorcher Ignite Ground pilot")
        self.roles = [BrowserRole("dm")]

    def run(self, base_url: str, pages: Dict[str, Page], collector: ArtifactCollector) -> bool:
        page = pages["dm"]

        # 1. POST to fixture
        logging.info("Seeding Scorcher fixture...")
        try:
            resp = requests.post(f"{base_url}/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground", timeout=10)
            resp.raise_for_status()
            fixture_data = resp.json()
        except Exception as e:
            logging.error(f"Fixture request failed: {e}")
            return False

        if not fixture_data.get("ok"):
            logging.error(f"Fixture returned error: {fixture_data.get('error')}")
            return False

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
             return False

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
            return False

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
            return False

        collector.capture_screenshot(page, "success_final")
        logging.info("Scenario scorcher-ignite-ground completed successfully.")
        return True

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
        if self.process:
            logging.info("Stopping local server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

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

    args = parser.parse_args()

    registry = Registry()
    registry.register(ScorcherIgniteGroundScenario())

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

            try:
                success = scenario.run(args.base_url, role_pages, collector)
            except Exception as e:
                logging.error(f"Scenario execution failed: {e}")
                error_msg = str(e)
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
        }
    }
    collector.write_summary(summary)
    logging.info(f"Artifact directory: {collector.run_dir}")

    if not success:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()

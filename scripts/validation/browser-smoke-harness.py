#!/usr/bin/env python3
"""
Browser Smoke Harness Shell (Gate 3)
Provides the CLI and artifact collection foundation for automated browser smoke tests.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Constants
DEFAULT_ARTIFACT_ROOT = Path("logs/browser-smoke")
DEFAULT_BASE_URL = "http://localhost:8000"

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

    def run(self, base_url: str, artifact_collector: ArtifactCollector) -> bool:
        """Runs the scenario. To be implemented by subclasses in Gate 4+."""
        raise NotImplementedError(f"Scenario '{self.id}' not implemented until Gate 4")

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
    def __init__(self, root: Path):
        self.root = root
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.root / self.timestamp
        self._initialized = False

    def ensure_initialized(self):
        if not self._initialized:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._initialized = True

    def write_summary(self, data: Dict[str, Any]):
        self.ensure_initialized()
        summary_path = self.run_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_path(self, filename: str) -> Path:
        self.ensure_initialized()
        return self.run_dir / filename

class ServerHandle:
    """Abstraction for managing a tracker server instance."""
    def __init__(self, base_url: str, is_external: bool = True):
        self.base_url = base_url
        self.is_external = is_external
        self.process = None

    def start(self):
        if self.is_external:
            logging.info(f"Using external server at {self.base_url}")
            return
        # Future: implement internal server launch for local isolation
        raise NotImplementedError("Internal server launch not implemented in Gate 3")

    def stop(self):
        if self.process:
            # Future: implement process termination
            pass

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

    args = parser.parse_args()

    registry = Registry()
    
    # Register stubs for upcoming scenarios
    scorcher_stub = Scenario("scorcher-ignite-ground", "Pilot: Scorcher Ignite Ground / Apply Result (Pending Gate 4)")
    scorcher_stub.roles = [BrowserRole("dm")]
    registry.register(scorcher_stub)

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

    # For Gate 3, we explicitly fail on the scorcher scenario as it's not implemented yet
    if scenario.id == "scorcher-ignite-ground":
        logging.error(f"Scenario '{scenario.id}' is registered but not implemented until Gate 4.")
        
        # We still demonstrate artifact collection as required by Gate 3
        collector = ArtifactCollector(args.artifact_root)
        summary = {
            "scenario": scenario.id,
            "timestamp": collector.timestamp,
            "status": "not_implemented",
            "roles": [r.name for r in scenario.roles],
            "artifacts": {
                "server_log": str(collector.get_path("server.log")),
                "screenshots": [],
                "traces": []
            },
            "browser_context_metadata": {
                role.name: role.context_metadata for role in scenario.roles
            }
        }
        collector.write_summary(summary)
        logging.info(f"Artifact directory created: {collector.run_dir}")
        sys.exit(1)

    # Future: run implementation
    sys.exit(0)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ship_blueprints import export_normalized_blueprint, import_tiled_json_file


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Tiled-authored ship JSON into normalized composite ship blueprint JSON."
    )
    parser.add_argument(
        "--source-dir",
        default="assets/ships/source_tiled",
        help="Directory containing *.tiled.json ship source files",
    )
    parser.add_argument(
        "--output-dir",
        default="assets/ships/blueprints",
        help="Directory to write normalized *.json ship blueprints",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        default=[],
        help="Optional blueprint ids to import (default imports all sources).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = REPO_ROOT
    source_dir = (repo_root / args.source_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}", file=sys.stderr)
        return 2
    requested_ids = {str(value).strip().lower() for value in (args.ids or []) if str(value).strip()}
    source_files = sorted(source_dir.glob("*.tiled.json"))
    if requested_ids:
        source_files = [path for path in source_files if path.stem.replace(".tiled", "").lower() in requested_ids]
    if not source_files:
        print("No source files matched.")
        return 1
    failures = 0
    for source_path in source_files:
        blueprint_id = source_path.stem.replace(".tiled", "").strip().lower()
        try:
            normalized = import_tiled_json_file(source_path, blueprint_id=blueprint_id)
            target_path = output_dir / f"{blueprint_id}.json"
            export_normalized_blueprint(target_path, normalized)
            print(f"Imported {source_path.name} -> {target_path.relative_to(repo_root)}")
        except Exception as exc:
            failures += 1
            print(f"FAILED {source_path.name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate current git changes against a repo-local AGY task scope JSON."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CURRENT_WORK_PATH = "docs/work_items/current_work.md"


@dataclass(frozen=True)
class Scope:
    task_id: str
    allowed_edit_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    forbidden_diff_patterns: tuple[str, ...]
    allow_work_close: bool
    allow_commit: bool
    required_clean_staging: bool
    baseline_allowed_dirty_paths: tuple[str, ...]
    allow_untracked_outside_allowed: bool = False


def info(kind: str, message: str) -> None:
    print(f"[{kind}] {message}")


def run_git(args: list[str], *, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if isinstance(result.stderr, str) else result.stderr
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def repo_root() -> Path:
    output = run_git(["rev-parse", "--show-toplevel"])
    return Path(str(output).strip()).resolve()


def normalize_path(path: str, root: Path) -> str:
    raw = path.replace("\\", "/").strip()
    if not raw:
        return ""
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            raw = candidate.resolve().relative_to(root).as_posix()
        except ValueError:
            raw = candidate.resolve().as_posix()
    raw = raw.replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    return os.path.normpath(raw).replace("\\", "/").rstrip("/") if raw != "." else "."


def normalize_prefix(path: str, root: Path) -> str:
    normalized = normalize_path(path, root)
    return normalized.rstrip("/") + "/" if path.replace("\\", "/").endswith("/") else normalized


def load_scope(path: Path, root: Path) -> Scope:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    required = {
        "task_id": str,
        "allowed_edit_paths": list,
        "forbidden_paths": list,
        "forbidden_diff_patterns": list,
        "allow_work_close": bool,
        "allow_commit": bool,
        "required_clean_staging": bool,
    }
    for key, expected_type in required.items():
        if key not in data:
            raise ValueError(f"Scope JSON missing required key: {key}")
        if not isinstance(data[key], expected_type):
            raise ValueError(
                f"Scope JSON key {key!r} must be {expected_type.__name__}, "
                f"got {type(data[key]).__name__}"
            )

    baseline = data.get("baseline_allowed_dirty_paths", [])
    if not isinstance(baseline, list):
        raise ValueError("Scope JSON key 'baseline_allowed_dirty_paths' must be list[str]")

    allow_untracked = data.get("allow_untracked_outside_allowed", False)
    if not isinstance(allow_untracked, bool):
        raise ValueError("Scope JSON key 'allow_untracked_outside_allowed' must be bool")

    def normalize_list(key: str) -> tuple[str, ...]:
        values: list[Any] = data.get(key, [])
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str):
                raise ValueError(f"Scope JSON key {key!r} must contain only strings")
            normalized.append(normalize_prefix(value, root))
        return tuple(normalized)

    return Scope(
        task_id=data["task_id"],
        allowed_edit_paths=normalize_list("allowed_edit_paths"),
        forbidden_paths=normalize_list("forbidden_paths"),
        forbidden_diff_patterns=tuple(data["forbidden_diff_patterns"]),
        allow_work_close=data["allow_work_close"],
        allow_commit=data["allow_commit"],
        required_clean_staging=data["required_clean_staging"],
        baseline_allowed_dirty_paths=tuple(
            normalize_prefix(value, root) for value in baseline if isinstance(value, str)
        ),
        allow_untracked_outside_allowed=allow_untracked,
    )


def split_nul(output: bytes) -> set[str]:
    if not output:
        return set()
    return {part.decode("utf-8", "replace") for part in output.split(b"\0") if part}


def changed_paths(root: Path) -> tuple[set[str], set[str], set[str]]:
    staged = {
        normalize_path(path, root)
        for path in split_nul(run_git(["diff", "--cached", "--name-only", "-z"], text=False))
    }
    unstaged = {
        normalize_path(path, root)
        for path in split_nul(run_git(["diff", "--name-only", "-z"], text=False))
    }
    untracked = {
        normalize_path(path, root)
        for path in split_nul(
            run_git(["ls-files", "--others", "--exclude-standard", "-z"], text=False)
        )
    }
    return staged, unstaged, untracked


def matches_path(path: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/"):
            if path.startswith(pattern):
                return True
        elif path == pattern or path.startswith(pattern + "/"):
            return True
    return False


def diff_text(untracked: set[str], scope: Scope) -> str:
    unstaged = run_git(["diff", "--no-ext-diff", "--"])
    staged = run_git(["diff", "--cached", "--no-ext-diff", "--"])
    untracked_parts: list[str] = []
    for path in sorted(untracked):
        if matches_path(path, scope.baseline_allowed_dirty_paths):
            continue
        if not matches_path(path, scope.allowed_edit_paths):
            continue
        file_path = Path(path)
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            untracked_parts.append(f"\n--- unreadable untracked file {path}: {exc}\n")
            continue
        untracked_parts.append(f"\n--- untracked file {path}\n{text}")
    return f"{unstaged}\n{staged}\n{''.join(untracked_parts)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope_json", help="Path to AGY task scope JSON")
    args = parser.parse_args()

    root = repo_root()
    os.chdir(root)

    try:
        scope = load_scope(Path(args.scope_json), root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        info("FAIL", f"Could not load scope JSON: {exc}")
        return 2

    failures: list[str] = []
    warnings: list[str] = []
    staged, unstaged, untracked = changed_paths(root)
    all_changed = staged | unstaged | untracked

    info("PASS", f"Loaded scope {scope.task_id}")

    if staged:
        staged_list = ", ".join(sorted(staged))
        if scope.required_clean_staging:
            failures.append(f"Staged changes are forbidden by required_clean_staging: {staged_list}")
        if not scope.allow_commit:
            failures.append(f"Staged changes exist while allow_commit=false: {staged_list}")
    else:
        info("PASS", "No staged changes detected")

    for path in sorted(all_changed):
        if matches_path(path, scope.baseline_allowed_dirty_paths):
            warnings.append(f"Baseline dirty path ignored for scope enforcement: {path}")
            continue
        if path in untracked and scope.allow_untracked_outside_allowed:
            warnings.append(f"Untracked path outside allowed scope ignored by policy: {path}")
            continue
        if not matches_path(path, scope.allowed_edit_paths):
            failures.append(f"Changed path outside allowed_edit_paths: {path}")

    for path in sorted(all_changed):
        if matches_path(path, scope.baseline_allowed_dirty_paths):
            continue
        if matches_path(path, scope.forbidden_paths):
            failures.append(f"Forbidden path changed: {path}")

    if CURRENT_WORK_PATH in all_changed and not scope.allow_work_close:
        failures.append(
            f"{CURRENT_WORK_PATH} changed while allow_work_close=false"
        )

    content = diff_text(untracked, scope)
    for pattern in scope.forbidden_diff_patterns:
        if pattern in content:
            failures.append(f"Forbidden diff pattern found: {pattern!r}")

    if not failures:
        info("PASS", "All changed paths are within allowed_edit_paths or baseline allowances")
        info("PASS", "No forbidden paths or diff patterns detected")

    for warning in warnings:
        info("WARN", warning)
    for failure in failures:
        info("FAIL", failure)

    if failures:
        info("FAIL", f"Scope validation failed for {scope.task_id}")
        return 1

    info("PASS", f"Scope validation passed for {scope.task_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        info("FAIL", str(exc))
        raise SystemExit(2)

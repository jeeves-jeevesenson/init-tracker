#!/usr/bin/env python3
"""Conservative AGY hook command guard for migration-mode tasks."""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Any, Iterable


COMMAND_KEYS = {
    "cmd",
    "command",
    "shell",
    "shell_command",
    "script",
    "input",
    "args",
    "arguments",
}

BLOCKED_PATHS = (
    "logs/context/",
    "docs/bug_reports/inbox/",
)


def warn(message: str) -> None:
    print(f"[WARN] {message}", file=sys.stderr)


def block(reason: str) -> None:
    print(f"[BLOCK] {reason}", file=sys.stderr)
    raise SystemExit(1)


def load_payload() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        warn("No hook payload on stdin; allowing command.")
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        warn(f"Could not parse hook payload as JSON ({exc}); allowing command.")
        return None


def likely_command_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    command_heads = (
        "git ",
        "pytest",
        "python ",
        "python3 ",
        "grep ",
        "find ",
        "rm ",
        "bash ",
        "sh ",
        "timeout ",
    )
    return stripped.startswith(command_heads) or "\n" in stripped


def extract_commands(payload: Any, key_path: tuple[str, ...] = ()) -> Iterable[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lower_key = str(key).lower()
            next_path = (*key_path, lower_key)
            if isinstance(value, str) and (
                lower_key in COMMAND_KEYS or likely_command_string(value)
            ):
                yield value
            else:
                yield from extract_commands(value, next_path)
    elif isinstance(payload, list):
        for value in payload:
            yield from extract_commands(value, key_path)
    elif isinstance(payload, str) and likely_command_string(payload):
        yield payload


def split_shell_lines(command: str) -> Iterable[str]:
    for line in command.splitlines():
        for part in re.split(r"\s*(?:&&|\|\||;)\s*", line):
            stripped = part.strip()
            if stripped:
                yield stripped


def tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        warn(f"Could not shell-tokenize command; allowing: {command!r}")
        return []


def normalized_command(tokens: list[str]) -> list[str]:
    if len(tokens) >= 2 and tokens[0] == "timeout":
        return tokens[2:]
    return tokens


def is_pytest_command(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if tokens[0].endswith("pytest") or tokens[0] == "pytest":
        return True
    return len(tokens) >= 3 and tokens[0] in {"python", "python3"} and tokens[1:3] == [
        "-m",
        "pytest",
    ]


def pytest_has_scope(tokens: list[str]) -> bool:
    if tokens[0] in {"python", "python3"}:
        args = tokens[3:]
    else:
        args = tokens[1:]
    for token in args:
        if token.startswith("-"):
            continue
        if token == "--":
            continue
        if token.endswith(".py") or token.startswith("tests/") or "/" in token:
            return True
    return False


def touches_blocked_path(command: str) -> str | None:
    normalized = command.replace("\\", "/")
    for path in BLOCKED_PATHS:
        if path in normalized:
            return path
    return None


def check_command(command: str) -> None:
    blocked_path = touches_blocked_path(command)
    if blocked_path:
        block(f"Command touches off-scope path {blocked_path}: {command}")

    for part in split_shell_lines(command):
        tokens = normalized_command(tokenize(part))
        if not tokens:
            continue

        if tokens[:2] == ["git", "commit"]:
            block("git commit is blocked in migration-mode tasks.")
        if tokens[:2] == ["git", "push"]:
            block("git push is blocked in migration-mode tasks.")
        if tokens[:2] == ["git", "add"] and any(
            token in {".", "-A", "--all"} for token in tokens[2:]
        ):
            block("Broad git add is blocked; stage explicit files only when allowed.")

        if is_pytest_command(tokens) and not pytest_has_scope(tokens):
            block("Unscoped pytest is blocked; provide explicit test files or paths.")

        if tokens[0] == "grep" and any(
            token in {"-r", "-R", "--recursive"} or ("r" in token and token.startswith("-"))
            for token in tokens[1:]
        ):
            if "." in tokens[1:] or len(tokens) <= 3:
                block("Recursive grep from repo root is blocked.")

        if tokens[0] == "find" and len(tokens) > 1 and tokens[1] in {".", "./"}:
            block("Recursive find from repo root is blocked.")

        if tokens[0] == "rm" and any(
            token.startswith("-") and "r" in token and "f" in token
            for token in tokens[1:]
        ):
            block("rm -rf is blocked in migration-mode tasks.")


def main() -> int:
    payload = load_payload()
    if payload is None:
        return 0

    commands = list(dict.fromkeys(extract_commands(payload)))
    if not commands:
        warn("No shell command found in hook payload; allowing tool call.")
        return 0

    for command in commands:
        check_command(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

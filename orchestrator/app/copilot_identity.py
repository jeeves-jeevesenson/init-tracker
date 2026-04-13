from __future__ import annotations

DOCUMENTED_COPILOT_ASSIGNEE_LOGIN = "copilot-swe-agent[bot]"

_LEGACY_LOGIN_ALIASES = {
    "copilot": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "copilot-swe-agent": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "copilot-swe-agent[bot]": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "github-copilot": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "github-copilot[bot]": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
}

_COPILOT_DISPLAY_NAME_ALIASES = {
    "copilot",
    "github copilot",
    "copilot coding agent",
    "copilot swe agent",
    "copilot copilot swe agent",
}


def normalize_login(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def normalize_copilot_login(value: str | None) -> str:
    normalized = normalize_login(value)
    if not normalized:
        return normalize_login(DOCUMENTED_COPILOT_ASSIGNEE_LOGIN)
    return _LEGACY_LOGIN_ALIASES.get(normalized, normalized)


def normalize_display_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = "".join(char if char.isalnum() or char.isspace() else " " for char in normalized)
    return " ".join(normalized.split())


def normalize_configured_copilot_login(value: str | None) -> tuple[str, bool]:
    normalized = normalize_login(value)
    canonical = normalize_copilot_login(value)
    return canonical, canonical != normalized


def is_copilot_identity(login: str | None, configured_login: str | None) -> bool:
    normalized_login = normalize_copilot_login(login)
    configured_canonical, _ = normalize_configured_copilot_login(configured_login)
    return bool(login) and normalized_login == configured_canonical


def is_copilot_actor(*, login: str | None, display_name: str | None, configured_login: str | None) -> bool:
    if is_copilot_identity(login, configured_login):
        return True

    normalized_login = normalize_login(login)
    if normalized_login in {"copilot", "copilot-swe-agent", "copilot-swe-agent[bot]"}:
        return True

    normalized_display_name = normalize_display_name(display_name)
    if not normalized_display_name:
        return False
    if normalized_display_name in _COPILOT_DISPLAY_NAME_ALIASES:
        return True
    return "copilot" in normalized_display_name and (
        "agent" in normalized_display_name or "github" in normalized_display_name or "swe" in normalized_display_name
    )

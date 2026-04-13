from __future__ import annotations

DOCUMENTED_COPILOT_ASSIGNEE_LOGIN = "copilot-swe-agent[bot]"

_LEGACY_LOGIN_ALIASES = {
    "copilot-swe-agent": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "copilot-swe-agent[bot]": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "github-copilot": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
    "github-copilot[bot]": DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
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


def normalize_configured_copilot_login(value: str | None) -> tuple[str, bool]:
    normalized = normalize_login(value)
    canonical = normalize_copilot_login(value)
    return canonical, canonical != normalized


def is_copilot_identity(login: str | None, configured_login: str | None) -> bool:
    normalized_login = normalize_copilot_login(login)
    configured_canonical, _ = normalize_configured_copilot_login(configured_login)
    return bool(login) and normalized_login == configured_canonical

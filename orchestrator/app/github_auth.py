"""GitHub auth helpers with explicit dispatch/governor auth lanes.

Dispatch lane:
- issue-assignment and actor-query operations
- uses GITHUB_DISPATCH_USER_TOKEN (fallback: GITHUB_API_TOKEN)

Governor lane:
- neutral PR lifecycle governance operations (reviews/merge/reviewer cleanup/inspection)
- mode from GITHUB_GOVERNOR_AUTH_MODE (fallback: GITHUB_AUTH_MODE)
- token mode uses GITHUB_API_TOKEN
- app mode mints GitHub App installation token
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .config import Settings

logger = logging.getLogger(__name__)


@dataclass
class _CachedInstallationToken:
    """Holds a cached installation access token and its expiry."""
    token: str = ""
    expires_at: float = 0.0  # unix timestamp


_token_cache = _CachedInstallationToken()
_token_lock = threading.Lock()

# Tokens are valid for ~60 min; refresh when < 5 min remain.
_REFRESH_MARGIN_SECONDS = 300
_DEFAULT_TOKEN_LIFETIME_SECONDS = 3600


def _debug_github_enabled(settings: "Settings") -> bool:
    return bool(getattr(settings, "orchestrator_debug_github", False))


def _log_auth_debug(
    settings: "Settings",
    *,
    event: str,
    auth_lane: str,
    success: bool,
    summary: str,
    credential_present: bool | None = None,
    validation_succeeded: bool | None = None,
    http_status: int | None = None,
    result_class: str | None = None,
) -> None:
    if not _debug_github_enabled(settings):
        return
    logger.info(
        "github_debug event=%s auth_lane=%s credential_present=%s validation_succeeded=%s http_status=%s result_class=%s success=%s summary=%s",
        event,
        auth_lane,
        credential_present if credential_present is not None else "n/a",
        validation_succeeded if validation_succeeded is not None else "n/a",
        http_status if http_status is not None else "n/a",
        result_class or "n/a",
        success,
        summary,
    )


def _read_private_key(path: str) -> str:
    """Read PEM private key from disk.  Raises on missing/empty file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"GitHub App private key not found: {path}")
    content = p.read_text().strip()
    if not content:
        raise ValueError(f"GitHub App private key file is empty: {path}")
    return content


def _generate_app_jwt(*, client_id: str, private_key_pem: str, now: float | None = None) -> str:
    """Create a short-lived JWT for GitHub App authentication.

    Uses ``client_id`` as the JWT ``iss`` claim (GitHub's recommended approach
    for new apps).
    """
    import jwt  # PyJWT

    now_ts = int(now or time.time())
    payload = {
        "iat": now_ts - 60,  # small clock-skew buffer
        "exp": now_ts + 600,  # 10-minute max lifetime
        "iss": client_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def _exchange_jwt_for_installation_token(
    *,
    jwt_token: str,
    installation_id: str,
    api_base: str,
) -> tuple[str, float]:
    """Exchange App JWT for an installation access token.

    Returns ``(token, expires_at_unix)``.
    Raises on HTTP or parse errors.
    """
    url = f"{api_base}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {jwt_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(
            f"GitHub installation token exchange failed ({response.status_code}): "
            f"{response.text[:500]}"
        )
    body = response.json()
    token = body.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("GitHub installation token exchange returned empty token")
    # Parse expires_at ISO string → unix timestamp
    expires_at_str = body.get("expires_at", "")
    try:
        from datetime import datetime, timezone
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        expires_at = time.time() + _DEFAULT_TOKEN_LIFETIME_SECONDS
    return token, expires_at


def _mint_installation_token(settings: "Settings") -> str:
    """Mint (or return cached) installation access token.

    Thread-safe. Refreshes when within ``_REFRESH_MARGIN_SECONDS`` of expiry.
    """
    now = time.time()
    with _token_lock:
        if _token_cache.token and _token_cache.expires_at - now > _REFRESH_MARGIN_SECONDS:
            return _token_cache.token

    # Validate config outside lock
    client_id = settings.github_app_client_id
    installation_id = settings.github_app_installation_id
    key_path = settings.github_app_private_key_path
    if not client_id or not installation_id or not key_path:
        raise RuntimeError(
            "Governor app auth is misconfigured: "
            f"client_id={'set' if client_id else 'MISSING'}, "
            f"installation_id={'set' if installation_id else 'MISSING'}, "
            f"private_key_path={'set' if key_path else 'MISSING'}"
        )

    private_key = _read_private_key(key_path)
    jwt_token = _generate_app_jwt(client_id=client_id, private_key_pem=private_key, now=now)
    api_base = settings.github_api_url.rstrip("/")
    token, expires_at = _exchange_jwt_for_installation_token(
        jwt_token=jwt_token,
        installation_id=installation_id,
        api_base=api_base,
    )

    with _token_lock:
        _token_cache.token = token
        _token_cache.expires_at = expires_at
    logger.info(
        "GitHub App installation token minted (expires in %.0fs)",
        expires_at - time.time(),
    )
    return token


# ---------------------------------------------------------------------------
# Public API (explicit lanes)
# ---------------------------------------------------------------------------

def _normalized_governor_mode(settings: "Settings") -> str:
    configured = getattr(settings, "github_governor_auth_mode", None)
    if isinstance(configured, str) and configured.strip():
        mode = configured.strip().lower()
    else:
        mode = str(getattr(settings, "github_auth_mode", "token") or "token").strip().lower()
    return "app" if mode == "app" else "token"


def _base_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def is_governor_app_mode(settings: "Settings") -> bool:
    """Return True when governor auth is configured for GitHub App mode."""
    return _normalized_governor_mode(settings) == "app"


def has_dispatch_auth(settings: "Settings") -> bool:
    """Return True when dispatch auth can use a user token."""
    ready = bool(settings.github_dispatch_user_token or settings.github_api_token)
    _log_auth_debug(
        settings,
        event="dispatch_auth_checked",
        auth_lane="dispatch_user_token",
        credential_present=ready,
        validation_succeeded=ready,
        success=ready,
        result_class="auth_ready" if ready else "auth_missing",
        summary=dispatch_auth_label(settings),
    )
    return ready


def get_dispatch_token(settings: "Settings") -> str:
    """Return dispatch user token (explicit token preferred; legacy fallback)."""
    token = settings.github_dispatch_user_token or settings.github_api_token
    if not token:
        raise RuntimeError(
            "Dispatch auth failure: dispatch user token missing "
            "(set GITHUB_DISPATCH_USER_TOKEN or legacy GITHUB_API_TOKEN)"
        )
    return token


def build_dispatch_auth_headers(settings: "Settings") -> dict[str, str]:
    """Build headers for dispatch lane operations."""
    headers = _base_headers()
    try:
        token = get_dispatch_token(settings)
        headers["Authorization"] = f"Bearer {token}"
    except RuntimeError as exc:
        logger.warning("Unable to obtain dispatch auth token: %s", exc)
    return headers


def dispatch_auth_label(settings: "Settings") -> str:
    if settings.github_dispatch_user_token:
        return "dispatch user token (GITHUB_DISPATCH_USER_TOKEN)"
    if settings.github_api_token:
        return "legacy token fallback (GITHUB_API_TOKEN)"
    return "missing dispatch token"


def has_governor_auth(settings: "Settings") -> bool:
    """Return True when governor auth config is available."""
    if is_governor_app_mode(settings):
        ready = bool(
            settings.github_app_client_id
            and settings.github_app_installation_id
            and settings.github_app_private_key_path
        )
        _log_auth_debug(
            settings,
            event="governor_auth_checked",
            auth_lane="governor_app",
            credential_present=ready,
            validation_succeeded=ready,
            success=ready,
            result_class="auth_ready" if ready else "auth_missing",
            summary=governor_auth_mode_label(settings),
        )
        return ready
    ready = bool(settings.github_api_token)
    _log_auth_debug(
        settings,
        event="governor_auth_checked",
        auth_lane="governor_token",
        credential_present=ready,
        validation_succeeded=ready,
        success=ready,
        result_class="auth_ready" if ready else "auth_missing",
        summary=governor_auth_mode_label(settings),
    )
    return ready


def get_governor_token(settings: "Settings") -> str:
    """Return governor auth token based on governor auth mode."""
    if is_governor_app_mode(settings):
        return _mint_installation_token(settings)
    token = settings.github_api_token
    if not token:
        raise RuntimeError(
            "Governor auth failure: GITHUB_API_TOKEN is not configured for governor token mode"
        )
    return token


def build_governor_auth_headers(settings: "Settings") -> dict[str, str]:
    """Build headers for governor lane operations."""
    headers = _base_headers()
    try:
        token = get_governor_token(settings)
        headers["Authorization"] = f"Bearer {token}"
    except RuntimeError as exc:
        mode = _normalized_governor_mode(settings)
        logger.warning("Unable to obtain governor auth token in %s mode: %s", mode, exc)
    return headers


def governor_auth_mode_label(settings: "Settings") -> str:
    if is_governor_app_mode(settings):
        return "app (GitHub App installation token)"
    return "token (GITHUB_API_TOKEN)"


def try_mint_governor_app_token(settings: "Settings") -> tuple[bool, str]:
    """Attempt to mint governor app token, returning (ok, message)."""
    if not is_governor_app_mode(settings):
        return False, "Governor auth mode is not 'app'"
    try:
        _mint_installation_token(settings)
        _log_auth_debug(
            settings,
            event="governor_app_token_mint",
            auth_lane="governor_app",
            credential_present=True,
            validation_succeeded=True,
            success=True,
            result_class="mint_ok",
            summary="Installation token minted successfully",
        )
        return True, "Installation token minted successfully"
    except Exception as exc:
        _log_auth_debug(
            settings,
            event="governor_app_token_mint",
            auth_lane="governor_app",
            credential_present=True,
            validation_succeeded=False,
            success=False,
            result_class="mint_failed",
            summary=f"Installation token minting failed: {exc}",
        )
        return False, f"Installation token minting failed: {exc}"


# ---------------------------------------------------------------------------
# Backward-compatible shared helper aliases (governor lane semantics)
# ---------------------------------------------------------------------------

def is_app_mode(settings: "Settings") -> bool:
    return is_governor_app_mode(settings)


def has_github_auth(settings: "Settings") -> bool:
    return has_governor_auth(settings)


def get_github_token(settings: "Settings") -> str:
    return get_governor_token(settings)


def build_auth_headers(settings: "Settings") -> dict[str, str]:
    return build_governor_auth_headers(settings)


def auth_mode_label(settings: "Settings") -> str:
    if is_governor_app_mode(settings):
        return "app (GitHub App installation token)"
    return "token (legacy PAT)"


def try_mint_app_token(settings: "Settings") -> tuple[bool, str]:
    return try_mint_governor_app_token(settings)


def invalidate_cached_token() -> None:
    """Clear the cached installation token (useful for testing)."""
    with _token_lock:
        _token_cache.token = ""
        _token_cache.expires_at = 0.0

"""Shared GitHub auth helper — App installation tokens + legacy PAT fallback.

This module is the single source of outbound GitHub auth for the orchestrator.
All REST and GraphQL callers obtain tokens through :func:`get_github_token` or
build headers via :func:`build_auth_headers`.

Auth modes
----------
- ``token``  (legacy): uses ``GITHUB_API_TOKEN`` directly.
- ``app``   (preferred): mints a GitHub App JWT from the configured PEM key,
  exchanges it for an installation access token, and caches/reuses the token
  until near expiry.

The active mode is determined by ``Settings.github_auth_mode``.
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
            "GitHub App auth is misconfigured: "
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
# Public API
# ---------------------------------------------------------------------------

def is_app_mode(settings: "Settings") -> bool:
    """Return True when the orchestrator is configured for GitHub App auth."""
    return str(getattr(settings, "github_auth_mode", "token") or "token").strip().lower() == "app"


def has_github_auth(settings: "Settings") -> bool:
    """Return True when *some* form of GitHub auth is available.

    - In token mode: ``github_api_token`` must be set.
    - In app mode: the three app config fields must be set (actual minting is
      deferred to first use).
    """
    if is_app_mode(settings):
        return bool(
            settings.github_app_client_id
            and settings.github_app_installation_id
            and settings.github_app_private_key_path
        )
    return bool(settings.github_api_token)


def get_github_token(settings: "Settings") -> str:
    """Return the current GitHub access token for outbound API calls.

    Raises ``RuntimeError`` when auth is not configured or token minting fails.
    """
    if is_app_mode(settings):
        return _mint_installation_token(settings)
    token = settings.github_api_token
    if not token:
        raise RuntimeError("GitHub API token (GITHUB_API_TOKEN) is not configured")
    return token


def build_auth_headers(settings: "Settings") -> dict[str, str]:
    """Build GitHub API request headers with current auth.

    Falls back gracefully — returns headers without Authorization when auth
    is unavailable (callers should pre-check via :func:`has_github_auth`).
    """
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        token = get_github_token(settings)
        headers["Authorization"] = f"Bearer {token}"
    except RuntimeError as exc:
        mode = "app" if is_app_mode(settings) else "token"
        logger.warning("Unable to obtain GitHub auth token in %s mode: %s", mode, exc)
    return headers


def auth_mode_label(settings: "Settings") -> str:
    """Human-readable description of the current auth mode."""
    if is_app_mode(settings):
        return "app (GitHub App installation token)"
    return "token (legacy PAT)"


def try_mint_app_token(settings: "Settings") -> tuple[bool, str]:
    """Attempt to mint an app installation token, returning (ok, message).

    Used by preflight to report whether app auth is actually usable.
    """
    if not is_app_mode(settings):
        return False, "Auth mode is not 'app'"
    try:
        _mint_installation_token(settings)
        return True, "Installation token minted successfully"
    except Exception as exc:
        return False, f"Installation token minting failed: {exc}"


def invalidate_cached_token() -> None:
    """Clear the cached installation token (useful for testing)."""
    with _token_lock:
        _token_cache.token = ""
        _token_cache.expires_at = 0.0

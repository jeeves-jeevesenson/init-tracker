"""
Update checker module for D&D Initiative Tracker.
Checks for updates from GitHub releases and main branch.
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# GitHub repository information
REPO_OWNER = "jeeves-jeevesenson"
REPO_NAME = "init-tracker"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
EXPECTED_REPO_SLUG = f"{REPO_OWNER}/{REPO_NAME}".lower()


def get_current_version() -> str:
    """Get the current version of the application."""
    version_file = os.path.join(os.path.dirname(__file__), "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback to APP_VERSION from main file if VERSION file doesn't exist
        return "41"


def check_latest_release() -> Optional[Dict]:
    """Check GitHub for the latest release.
    
    Returns:
        Dict with 'tag_name', 'name', 'html_url', 'published_at' if available, None otherwise
    """
    try:
        url = f"{GITHUB_API_BASE}/releases/latest"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return {
                "tag_name": data.get("tag_name", ""),
                "name": data.get("name", ""),
                "html_url": data.get("html_url", ""),
                "published_at": data.get("published_at", ""),
                "body": data.get("body", "")
            }
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        logger.debug(f"Could not check latest release: {e}")
        return None


def check_main_branch_commit() -> Optional[Dict]:
    """Check GitHub for the latest commit on main branch.
    
    Returns:
        Dict with 'sha', 'commit' info if available, None otherwise
    """
    try:
        url = f"{GITHUB_API_BASE}/commits/main"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return {
                "sha": data.get("sha", ""),
                "short_sha": data.get("sha", "")[:7],
                "message": data.get("commit", {}).get("message", ""),
                "author": data.get("commit", {}).get("author", {}).get("name", ""),
                "date": data.get("commit", {}).get("author", {}).get("date", ""),
                "html_url": data.get("html_url", "")
            }
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        logger.debug(f"Could not check main branch: {e}")
        return None


def normalize_github_repo_slug(remote_url: str) -> Optional[str]:
    """Normalize a GitHub remote URL into owner/repo form."""
    if not remote_url:
        return None
    raw = str(remote_url).strip()
    if not raw:
        return None

    if raw.startswith("git@github.com:"):
        slug = raw.split("git@github.com:", 1)[1]
    else:
        try:
            parsed = urlparse(raw)
            host = (parsed.netloc or "").split("@")[-1].lower()
            if host != "github.com":
                return None
            slug = parsed.path.lstrip("/")
        except Exception:
            return None

    if slug.endswith(".git"):
        slug = slug[:-4]
    slug = slug.strip("/").lower()
    if slug.count("/") != 1:
        return None
    owner, repo = slug.split("/", 1)
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def get_local_git_remote_url(remote_name: str = "origin") -> Optional[str]:
    """Return the configured URL for a local git remote."""
    try:
        git_dir = os.path.join(os.path.dirname(__file__), ".git")
        if not os.path.exists(git_dir):
            return None
        result = subprocess.run(
            ["git", "remote", "get-url", remote_name],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        value = (result.stdout or "").strip()
        return value or None
    except Exception as e:
        logger.debug(f"Could not get local git remote URL: {e}")
        return None


def get_local_git_remote_slug(remote_name: str = "origin") -> Optional[str]:
    """Return local git remote in normalized owner/repo form."""
    url = get_local_git_remote_url(remote_name=remote_name)
    if not url:
        return None
    return normalize_github_repo_slug(url)


def is_supported_update_checkout() -> Tuple[bool, str]:
    """Return whether this checkout is safe for managed updater operations."""
    repo_dir = os.path.dirname(__file__)
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        return False, "This install is not a git checkout."

    remote_url = get_local_git_remote_url("origin")
    if not remote_url:
        return False, "No git origin remote is configured."

    slug = normalize_github_repo_slug(remote_url)
    if slug != EXPECTED_REPO_SLUG:
        return (
            False,
            f"Configured origin points to '{remote_url}', not '{EXPECTED_REPO_SLUG}'.",
        )

    return True, ""


def _is_managed_install_path(repo_dir: str) -> bool:
    """Detect managed quick-install style locations used by update scripts."""
    repo_norm = os.path.normpath(repo_dir)
    if sys.platform.startswith("win"):
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if not local_app_data:
            return False
        managed_root = os.path.normpath(os.path.join(local_app_data, "DnDInitiativeTracker"))
        return repo_norm.startswith(managed_root)
    home_dir = os.path.expanduser("~")
    managed_root = os.path.normpath(os.path.join(home_dir, ".local", "share", "dnd-initiative-tracker"))
    return repo_norm.startswith(managed_root)


def get_local_git_commit() -> Optional[str]:
    """Get the current local git commit SHA if in a git repository.
    
    Returns:
        Short commit SHA (7 chars) if available, None otherwise
    """
    try:
        git_dir = os.path.join(os.path.dirname(__file__), ".git")
        if not os.path.exists(git_dir):
            return None
        
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"Could not get local git commit: {e}")
    return None


def check_for_updates() -> Tuple[bool, str, Optional[Dict]]:
    """Check for available updates.
    
    Returns:
        Tuple of (has_update, message, update_info)
        - has_update: True if an update is available
        - message: Human-readable message about the update status
        - update_info: Dict with update details or None
    """
    current_version = get_current_version()
    local_commit = get_local_git_commit()
    local_slug = None
    is_official_checkout = False
    if local_commit:
        local_slug = get_local_git_remote_slug()
        is_official_checkout = local_slug == EXPECTED_REPO_SLUG
    
    # Check for latest release
    latest_release = check_latest_release()
    
    # Check main branch for updates
    latest_commit = check_main_branch_commit()
    
    # Determine if updates are available
    if latest_release:
        # Extract version number from tag (e.g., "v41" -> "41")
        release_version = latest_release["tag_name"].lstrip("v")
        try:
            if int(release_version) > int(current_version):
                message = f"New release available: {latest_release['tag_name']}\n"
                message += f"Current version: v{current_version}\n"
                if latest_release.get("name"):
                    message += f"\nRelease: {latest_release['name']}"
                return True, message, {"type": "release", "data": latest_release}
        except ValueError:
            pass
    
    # If we're in the official git repo, check if main branch has newer commits
    if local_commit and latest_commit and is_official_checkout:
        if latest_commit["short_sha"] != local_commit:
            message = f"New commits available on main branch\n"
            message += f"Your commit: {local_commit}\n"
            message += f"Latest commit: {latest_commit['short_sha']}\n"
            message += f"Message: {latest_commit['message'][:60]}..."
            return True, message, {"type": "commit", "data": latest_commit}
    
    # No updates available
    message = f"You are up to date! (v{current_version})"
    if local_commit:
        message += f"\nCommit: {local_commit}"
    if local_slug and not is_official_checkout:
        message += (
            f"\n\nNote: this checkout tracks '{local_slug}', so managed updater scripts are disabled."
        )
    return False, message, None


def get_update_command() -> Optional[str]:
    """Get the appropriate update command for the current platform and installation type.
    
    Returns:
        Command string to run for updating, or None if not applicable
    """
    script_dir = os.path.dirname(__file__)
    is_supported_repo, _reason = is_supported_update_checkout()
    if not is_supported_repo:
        return None
    if not _is_managed_install_path(script_dir):
        return None

    if sys.platform.startswith("win"):
        update_script = os.path.join(script_dir, "scripts", "update-windows.ps1")
        if os.path.exists(update_script):
            return f'powershell -ExecutionPolicy Bypass -File "{update_script}"'
    else:
        update_script = os.path.join(script_dir, "scripts", "update-linux.sh")
        if os.path.exists(update_script):
            return f'bash "{update_script}"'

    return None


def get_manual_update_instructions() -> str:
    """Return explicit safe update instructions for current checkout/install type."""
    repo_dir = os.path.dirname(__file__)
    is_supported_repo, reason = is_supported_update_checkout()
    in_managed_install = _is_managed_install_path(repo_dir)

    lines = [
        "Supported update paths:",
        "",
        "1) Source/developer checkout",
        "   - git fetch origin --prune",
        "   - git pull --ff-only origin main",
        "   - python -m pip install -r requirements.txt",
        "",
        "2) Managed local install (quick-install path)",
    ]
    if sys.platform.startswith("win"):
        lines.extend([
            "   - Close the app",
            r"   - Run: .\scripts\update-windows.ps1",
        ])
    else:
        lines.extend([
            "   - Close the app",
            "   - Run: ./scripts/update-linux.sh",
        ])

    if not is_supported_repo and reason:
        lines.extend([
            "",
            "Managed in-app updater is disabled for this checkout:",
            f"  {reason}",
            f"Only '{EXPECTED_REPO_SLUG}' is supported for managed updater scripts.",
        ])
    elif not in_managed_install:
        lines.extend([
            "",
            "This appears to be a source checkout, so in-app managed update scripts are not auto-launched.",
        ])
    return "\n".join(lines)

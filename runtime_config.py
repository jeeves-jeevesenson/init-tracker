from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


class RuntimeConfig:
    """Centralized path and environment configuration for the DnD Initiative Tracker.

    Supports both legacy (INITTRACKER_*) and new (INIT_TRACKER_*) environment variables.
    Provides sane defaults for development and structured paths for production/server mode.
    """

    def __init__(self) -> None:
        # 1. Basic Mode & Home
        self.mode = self._get_env("MODE", "development").lower()
        self.home = self._get_env("HOME")

        # 2. App Directory (Repository Root)
        # Default to the directory containing this file if not overridden.
        # Handle frozen (executable) environments.
        default_app_dir = str(Path(__file__).resolve().parent)
        try:
            if getattr(sys, "frozen", False):
                default_app_dir = str(Path(sys.executable).parent)
        except Exception:
            pass

        self.app_dir = Path(
            self._get_env("APP_DIR", default_app_dir)
        ).resolve()

        # 3. Data Directory
        # Production: Default to $INIT_TRACKER_HOME/data
        # Development: Default to ~/Documents/Dnd-Init-Yamls
        default_data_dir = ""
        if self.home:
            default_data_dir = str(Path(self.home).expanduser() / "data")
        else:
            try:
                default_data_dir = str(Path.home() / "Documents" / "Dnd-Init-Yamls")
            except Exception:
                default_data_dir = str(self.app_dir / "data")

        self.data_dir = Path(
            self._get_env("DATA_DIR", default_data_dir)
        ).expanduser().resolve()

        # 4. Log Directory
        # Production: Default to $INIT_TRACKER_HOME/logs
        # Development: Default to $DATA_DIR/logs
        default_log_dir = ""
        if self.home:
            default_log_dir = str(Path(self.home).expanduser() / "logs")
        else:
            default_log_dir = str(self.data_dir / "logs")

        self.log_dir = Path(
            self._get_env("LOG_DIR", default_log_dir)
        ).expanduser().resolve()

        # 5. Releases Directory
        # Production: Default to $INIT_TRACKER_HOME/releases
        # Development: Default to $DATA_DIR/releases
        default_releases_dir = ""
        if self.home:
            default_releases_dir = str(Path(self.home).expanduser() / "releases")
        else:
            default_releases_dir = str(self.data_dir / "releases")

        self.releases_dir = Path(
            self._get_env("RELEASES_DIR", default_releases_dir)
        ).expanduser().resolve()

        # 6. Network Settings
        self.host = self._get_env("HOST", "0.0.0.0")
        raw_port = self._get_env("PORT", "8787")
        try:
            self.port = int(raw_port)
        except (ValueError, TypeError):
            self.port = 8787
        self.public_base_url = self._get_env("PUBLIC_BASE_URL")

    def _get_env(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Lookup environment variable with preference for INIT_TRACKER_ prefix."""
        # Try INIT_TRACKER_NAME first
        val = os.getenv(f"INIT_TRACKER_{name}")
        if val is not None:
            return val
        # Try INITTRACKER_NAME (legacy)
        val = os.getenv(f"INITTRACKER_{name}")
        if val is not None:
            return val
        return default

    def is_production(self) -> bool:
        """True if running in production/server mode."""
        return self.mode in ("production", "server", "prod")

    def ensure_dirs(self) -> None:
        """Safely create required runtime directories if in production mode."""
        if not self.is_production():
            return

        # In production, we ensure these exist and are directories
        for d in (self.data_dir, self.log_dir, self.releases_dir):
            try:
                if not d.exists():
                    d.mkdir(parents=True, exist_ok=True)
            except Exception:
                # Best effort for directory creation
                pass

    def get_assets_dir(self) -> Path:
        """Returns the assets directory relative to app_dir."""
        return self.app_dir / "assets"

    def __repr__(self) -> str:
        return (
            f"RuntimeConfig(mode={self.mode!r}, "
            f"app_dir={self.app_dir}, "
            f"data_dir={self.data_dir}, "
            f"log_dir={self.log_dir})"
        )


# Singleton instance for easy access
config = RuntimeConfig()
if __name__ == "__main__":
    config.ensure_dirs()
    print(config)

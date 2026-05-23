from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", ""}
_TRACE_ID: ContextVar[Optional[str]] = ContextVar("init_tracker_trace_id", default=None)
_ACTION_ID: ContextVar[Optional[str]] = ContextVar("init_tracker_action_id", default=None)


class _DebugTraceState:
    def __init__(self) -> None:
        self.enabled = False
        self.path: Optional[Path] = None
        self.lock = threading.RLock()


_DEBUG_TRACE_STATE = _DebugTraceState()


def parse_bool_value(value: Any, *, default: Optional[bool] = None) -> Optional[bool]:
    """Parse user-facing bool values without treating "false" as truthy."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    raw = str(value).strip().lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return default


def debugging_env_enabled() -> bool:
    raw = os.getenv("INIT_TRACKER_DEBUGGING")
    if raw is None:
        raw = os.getenv("INITTRACKER_DEBUGGING")
    return bool(parse_bool_value(raw, default=False))


def tactical_map_enabled() -> bool:
    """Return whether experimental tactical map projections are enabled."""
    raw = os.getenv("INIT_TRACKER_ENABLE_TACTICAL_MAP")
    if raw is None:
        raw = os.getenv("INITTRACKER_ENABLE_TACTICAL_MAP")
    return bool(parse_bool_value(raw, default=False))


def ship_surfaces_enabled() -> bool:
    """Return whether experimental ship/surface/structure projections are enabled."""
    raw = os.getenv("INIT_TRACKER_ENABLE_SHIP_SURFACES")
    if raw is None:
        raw = os.getenv("INITTRACKER_ENABLE_SHIP_SURFACES")
    return bool(parse_bool_value(raw, default=False))


def _debug_trace_log_dir(log_dir: Optional[Path] = None) -> Path:
    return Path(log_dir) if log_dir is not None else Path("logs")


def configure_debug_trace(enabled: Optional[bool] = None, *, log_dir: Optional[Path] = None) -> Optional[Path]:
    """Enable or disable the opt-in live debug JSONL trace."""
    next_enabled = debugging_env_enabled() if enabled is None else bool(enabled)
    with _DEBUG_TRACE_STATE.lock:
        _DEBUG_TRACE_STATE.enabled = next_enabled
        if not next_enabled:
            _DEBUG_TRACE_STATE.path = None
            return None
        if _DEBUG_TRACE_STATE.path is None:
            base = _debug_trace_log_dir(log_dir)
            try:
                base.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            _DEBUG_TRACE_STATE.path = base / f"debug-trace-{stamp}.jsonl"
        return _DEBUG_TRACE_STATE.path


def debug_trace_enabled() -> bool:
    return bool(_DEBUG_TRACE_STATE.enabled)


def debug_trace_path() -> Optional[Path]:
    return _DEBUG_TRACE_STATE.path


def new_trace_id() -> str:
    return f"trace-{uuid.uuid4().hex}"


def new_action_id() -> str:
    return f"action-{uuid.uuid4().hex}"


def current_trace_id() -> Optional[str]:
    return _TRACE_ID.get()


def current_action_id() -> Optional[str]:
    return _ACTION_ID.get()


def current_debug_correlation() -> Dict[str, str]:
    correlation: Dict[str, str] = {}
    trace_id = current_trace_id()
    action_id = current_action_id()
    if trace_id:
        correlation["trace_id"] = trace_id
    if action_id:
        correlation["action_id"] = action_id
    return correlation


@contextmanager
def debug_context(*, trace_id: Optional[str] = None, action_id: Optional[str] = None) -> Iterator[None]:
    trace_token = _TRACE_ID.set(str(trace_id)) if trace_id else None
    action_token = _ACTION_ID.set(str(action_id)) if action_id else None
    try:
        yield
    finally:
        if action_token is not None:
            _ACTION_ID.reset(action_token)
        if trace_token is not None:
            _TRACE_ID.reset(trace_token)


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "<truncated>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, BaseException):
        return type(value).__name__
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return value[:1000]
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 80:
                out["_truncated"] = True
                break
            out[str(key)[:120]] = _json_safe(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, depth=depth + 1) for item in list(value)[:80]]
    return repr(value)[:1000]


def debug_event(event: str, **fields: Any) -> None:
    if not debug_trace_enabled():
        return
    entry: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "level": str(fields.pop("level", "debug") or "debug"),
        "event": str(event or "debug.event"),
        "trace_id": current_trace_id(),
        "span": fields.pop("span", None),
    }
    action_id = current_action_id()
    if action_id:
        entry["action_id"] = action_id
    for key, value in fields.items():
        if value is None:
            continue
        entry[str(key)] = _json_safe(value)
    path = debug_trace_path()
    if path is None:
        return
    try:
        line = json.dumps(entry, allow_nan=False, separators=(",", ":"), default=str)
        with _DEBUG_TRACE_STATE.lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:
        pass


@contextmanager
def timed_span(span: str, **fields: Any) -> Iterator[None]:
    if not debug_trace_enabled():
        yield
        return
    started_ns = time.perf_counter_ns()
    debug_event("span.start", span=span, **fields)
    ok = True
    reason: Optional[str] = None
    try:
        yield
    except BaseException as exc:
        ok = False
        reason = type(exc).__name__
        raise
    finally:
        duration_ms = round((time.perf_counter_ns() - started_ns) / 1_000_000.0, 3)
        debug_event("span.end", span=span, duration_ms=duration_ms, ok=ok, reason=reason, **fields)
        if duration_ms > 2000.0:
            debug_event("hang_candidate.span", span=span, duration_ms=duration_ms, ok=ok, reason=reason, **fields)
        elif duration_ms > 500.0:
            debug_event("very_slow.span", span=span, duration_ms=duration_ms, ok=ok, reason=reason, **fields)
        elif duration_ms > 100.0:
            debug_event("slow.span", span=span, duration_ms=duration_ms, ok=ok, reason=reason, **fields)


def timed_call(span: str, fn: Callable[..., Any], *args: Any, **fields: Any) -> Any:
    with timed_span(span, **fields):
        return fn(*args)


def _decorator_counts(receiver: Any) -> Optional[Dict[str, Any]]:
    counts_fn = getattr(receiver, "_debug_trace_counts", None)
    if not callable(counts_fn):
        tracker = getattr(receiver, "_tracker", None)
        counts_fn = getattr(tracker, "_debug_trace_counts", None)
    if not callable(counts_fn):
        return None
    try:
        counts = counts_fn()
    except Exception:
        return None
    return dict(counts) if isinstance(counts, dict) else None


def trace_timed(span: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Time a high-level function without logging argument bodies."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not debug_trace_enabled():
                return fn(*args, **kwargs)
            fields: Dict[str, Any] = {"function": fn.__qualname__}
            if args:
                counts = _decorator_counts(args[0])
                if counts:
                    fields["counts"] = counts
                for candidate in args[1:3]:
                    if isinstance(candidate, dict):
                        command = str(candidate.get("type") or "").strip()
                        if command:
                            fields["command"] = command
                        for key in ("spell_id", "spell_slug"):
                            if candidate.get(key) not in (None, ""):
                                fields[key] = candidate.get(key)
                        break
            for key in ("cid", "actor_cid", "target_cid", "ws_id", "scope"):
                if kwargs.get(key) not in (None, ""):
                    fields[key] = kwargs.get(key)
            with timed_span(span, **fields):
                return fn(*args, **kwargs)
        return wrapper
    return decorator


def with_action_correlation(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not debug_trace_enabled() or not isinstance(payload, dict):
        return payload
    correlation = current_debug_correlation()
    if not correlation:
        return payload
    merged = dict(payload)
    for key, value in correlation.items():
        merged.setdefault(key, value)
    return merged


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

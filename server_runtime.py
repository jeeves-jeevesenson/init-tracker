from __future__ import annotations

from typing import Any, Optional


class ServerRuntimeFacade:
    """Narrow facade skeleton between ASGI app and the legacy tracker runtime."""

    def __init__(self, lan_controller: Optional[Any] = None) -> None:
        self.lan_controller = lan_controller
        self._ready = False

    def start(self) -> None:
        """Mark the runtime facade ready for ASGI request handling."""
        self._ready = True

    def shutdown(self) -> None:
        """Mark the runtime facade no longer ready."""
        self._ready = False

    def is_ready(self) -> bool:
        """Return whether the runtime facade is ready."""
        return self._ready

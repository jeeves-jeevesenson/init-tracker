"""Server package boundary for the Initiative Tracker ASGI host."""

from init_tracker_server.app import create_app

__all__ = ["create_app"]

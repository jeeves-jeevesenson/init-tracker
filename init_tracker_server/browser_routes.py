from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Final, Tuple

from fastapi import FastAPI


BrowserEntryHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class BrowserEntryRouteHandlers:
    """Handlers owned by the caller for the browser entry routes."""

    index: BrowserEntryHandler
    planning: BrowserEntryHandler
    new_character: BrowserEntryHandler
    edit_character: BrowserEntryHandler
    shop_admin: BrowserEntryHandler
    shop: BrowserEntryHandler
    config_redirect: BrowserEntryHandler
    service_worker: BrowserEntryHandler


@dataclass(frozen=True)
class BrowserEntryRoute:
    method: str
    path: str
    endpoint_name: str


BROWSER_ENTRY_ROUTE_INVENTORY: Final[Tuple[BrowserEntryRoute, ...]] = (
    BrowserEntryRoute(method="GET", path="/", endpoint_name="index"),
    BrowserEntryRoute(method="GET", path="/planning", endpoint_name="planning"),
    BrowserEntryRoute(method="GET", path="/new_character", endpoint_name="new_character"),
    BrowserEntryRoute(method="GET", path="/edit_character", endpoint_name="edit_character"),
    BrowserEntryRoute(method="GET", path="/shop_admin", endpoint_name="shop_admin"),
    BrowserEntryRoute(method="GET", path="/shop", endpoint_name="shop"),
    BrowserEntryRoute(method="GET", path="/config", endpoint_name="config_redirect"),
    BrowserEntryRoute(method="GET", path="/sw.js", endpoint_name="service_worker"),
)


def register_browser_entry_routes(
    app: FastAPI,
    handlers: BrowserEntryRouteHandlers,
) -> None:
    """Register the browser entry routes after an all-or-nothing collision check."""

    existing_path_methods = {
        (str(route.path), str(method).upper())
        for route in app.routes
        if getattr(route, "path", None) is not None
        for method in (getattr(route, "methods", None) or ())
    }
    for route in BROWSER_ENTRY_ROUTE_INVENTORY:
        route_key = (route.path, route.method)
        if route_key in existing_path_methods:
            raise ValueError(
                "Cannot register browser entry route "
                f"{route.method} {route.path}: path/method collision."
            )

    for route in BROWSER_ENTRY_ROUTE_INVENTORY:
        app.add_api_route(
            route.path,
            getattr(handlers, route.endpoint_name),
            methods=[route.method],
            name=route.endpoint_name,
        )

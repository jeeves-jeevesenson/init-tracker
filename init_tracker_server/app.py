from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .runtime import ServerRuntimeFacade


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Set the readiness flag on startup
    if hasattr(app.state, "runtime") and app.state.runtime is not None:
        app.state.runtime.start()
    app.state.ready = True
    yield
    # Clear the readiness flag on shutdown
    app.state.ready = False
    if hasattr(app.state, "runtime") and app.state.runtime is not None:
        app.state.runtime.shutdown()


def create_app(lan_controller: Optional[Any] = None) -> FastAPI:
    """FastAPI app factory for the Initiative Tracker ASGI server."""
    app = FastAPI(lifespan=app_lifespan)
    app.state.ready = False
    app.state.lan_controller = lan_controller
    app.state.runtime = ServerRuntimeFacade(lan_controller=lan_controller)

    # Bounded health/readiness endpoints
    @app.get("/health")
    @app.get("/api/health")
    async def health():
        return JSONResponse(
            content={
                "status": "healthy",
                "ready": getattr(app.state, "ready", False),
            },
            status_code=200,
        )

    @app.get("/ready")
    @app.get("/api/ready")
    async def readiness():
        if getattr(app.state, "ready", False):
            return JSONResponse(content={"status": "ready"}, status_code=200)
        return JSONResponse(content={"status": "not ready"}, status_code=503)

    return app

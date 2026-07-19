from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .runtime import ServerRuntimeFacade
from .runtime_host import RuntimeHostAdapter, RuntimeHostLifecycleError


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    if app.state.runtime_lifespan_entered:
        raise RuntimeHostLifecycleError(
            "application runtime lifespan has already been entered"
        )
    app.state.runtime_lifespan_entered = True

    def create_runtime() -> ServerRuntimeFacade:
        runtime = ServerRuntimeFacade(lan_controller=app.state.lan_controller)
        app.state.runtime = runtime
        return runtime

    def warm_up_runtime(runtime: ServerRuntimeFacade) -> None:
        lan_controller = app.state.lan_controller
        warm_up = getattr(lan_controller, "warm_up", None)
        if callable(warm_up):
            warm_up(runtime)

    runtime_host = RuntimeHostAdapter(
        create_runtime,
        start_runtime=lambda current_runtime: current_runtime.start(),
        warm_up_runtime=warm_up_runtime,
        stop_runtime=lambda current_runtime: current_runtime.shutdown(),
    )
    app.state.runtime_host = runtime_host
    try:
        runtime_host.start()
    except BaseException:
        app.state.ready = False
        raise

    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False
        runtime_host.stop()


def create_app(lan_controller: Optional[Any] = None) -> FastAPI:
    """FastAPI app factory for the Initiative Tracker ASGI server."""
    app = FastAPI(lifespan=app_lifespan)
    app.state.ready = False
    app.state.lan_controller = lan_controller
    app.state.runtime_lifespan_entered = False
    app.state.runtime = None
    app.state.runtime_host = None

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

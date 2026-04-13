from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from sqlmodel import Session

from .db import get_session, init_db
from .github_webhooks import router as github_router
from .openai_webhooks import router as openai_router
from .runs import list_recent_runs, run_to_dict


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="init-orchestrator",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(github_router)
app.include_router(openai_router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/runs")
def get_runs(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    runs = list_recent_runs(session, limit=limit)
    return {"ok": True, "count": len(runs), "runs": [run_to_dict(run) for run in runs]}

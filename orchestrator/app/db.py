from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


def _ensure_database_parent_dir(database_url: str) -> None:
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return
    db_file = Path(database_url.removeprefix(sqlite_prefix))
    db_file.parent.mkdir(parents=True, exist_ok=True)


def _build_engine():
    settings = get_settings()
    _ensure_database_parent_dir(settings.database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_engine():
    return _build_engine()


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as session:
        yield session

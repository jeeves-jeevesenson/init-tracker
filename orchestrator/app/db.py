from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings
from .models import RunEvent


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


def _dedupe_existing_run_events() -> None:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        return
    table_name = RunEvent.__tablename__
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                DELETE FROM {table_name}
                WHERE id IN (
                    SELECT newer.id
                    FROM {table_name} AS newer
                    JOIN {table_name} AS older
                      ON newer.source = older.source
                     AND newer.external_id = older.external_id
                    WHERE newer.external_id IS NOT NULL
                      AND newer.id > older.id
                )
                """
            )
        )


def _ensure_run_event_indexes() -> None:
    engine = get_engine()
    table_name = RunEvent.__tablename__
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            connection.execute(
                text(
                    f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_{table_name}_source_external_id
                    ON {table_name} (source, external_id)
                    WHERE external_id IS NOT NULL
                    """
                )
            )
            return
        connection.execute(
            text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_{table_name}_source_external_id
                ON {table_name} (source, external_id)
                """
            )
        )


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())
    _dedupe_existing_run_events()
    _ensure_run_event_indexes()


def get_session():
    with Session(get_engine()) as session:
        yield session

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.repository import AnalysisRepository


@lru_cache(maxsize=1)
def get_db_engine() -> Engine:
    return create_db_engine()


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory(
        get_db_engine()
    )


def get_database_session() -> Iterator[Session]:
    session = get_session_factory()()

    try:
        yield session
    finally:
        session.close()


def get_analysis_repository(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> AnalysisRepository:
    return AnalysisRepository(
        session
    )


def dispose_database_resources() -> None:
    """
    Dispose cached SQLAlchemy resources on application shutdown.
    """
    if get_db_engine.cache_info().currsize:
        engine = get_db_engine()

        get_session_factory.cache_clear()
        engine.dispose()
        get_db_engine.cache_clear()
        return

    get_session_factory.cache_clear()

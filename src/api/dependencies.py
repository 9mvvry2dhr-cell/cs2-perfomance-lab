from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.job_repository import AnalysisJobRepository
from src.database.repository import AnalysisRepository
from src.ingestion.service import DemoIngestionService
from src.ingestion.storage import LocalDemoStorage


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


def get_analysis_job_repository(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> AnalysisJobRepository:
    return AnalysisJobRepository(
        session
    )


@lru_cache(maxsize=1)
def get_demo_storage() -> LocalDemoStorage:
    root = Path(
        os.environ.get(
            "DEMO_STORAGE_DIR",
            "data/uploads",
        )
    )

    return LocalDemoStorage(
        root
    )


def get_demo_ingestion_service(
    repository: Annotated[
        AnalysisJobRepository,
        Depends(get_analysis_job_repository),
    ],
    storage: Annotated[
        LocalDemoStorage,
        Depends(get_demo_storage),
    ],
) -> DemoIngestionService:
    return DemoIngestionService(
        storage=storage,
        job_repository=repository,
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

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.job_repository import AnalysisJobRepository
from src.database.repository import AnalysisRepository
from src.ingestion.service import (
    DEFAULT_MAX_ACTIVE_JOBS,
    DemoIngestionService,
)
from src.ingestion.storage import (
    DEFAULT_MAX_DEMO_BYTES,
    DEFAULT_MAX_STORAGE_BYTES,
    LocalDemoStorage,
)
from src.domain.identity import CurrentUser


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

    max_bytes = int(
        os.environ.get(
            "DEMO_MAX_BYTES",
            str(DEFAULT_MAX_DEMO_BYTES),
        )
    )

    max_total_bytes = int(
        os.environ.get(
            "DEMO_STORAGE_MAX_BYTES",
            str(DEFAULT_MAX_STORAGE_BYTES),
        )
    )

    return LocalDemoStorage(
        root,
        max_bytes=max_bytes,
        max_total_bytes=max_total_bytes,
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
    max_active_jobs = int(
        os.environ.get(
            "ANALYSIS_MAX_ACTIVE_JOBS",
            str(DEFAULT_MAX_ACTIVE_JOBS),
        )
    )

    return DemoIngestionService(
        storage=storage,
        job_repository=repository,
        max_active_jobs=max_active_jobs,
    )


def get_current_user() -> CurrentUser:
    """
    Resolve the authenticated product user.

    This is intentionally environment-backed for the local
    prototype. Steam login/session authentication will replace
    this implementation without changing protected API routes.
    """
    steam_id = (
        os.environ.get(
            "CURRENT_USER_STEAM_ID",
            "",
        )
        .strip()
    )

    if not steam_id:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Current user identity is not configured"
            ),
        )

    return CurrentUser(
        steam_id=steam_id
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

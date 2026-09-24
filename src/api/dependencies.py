from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import (
    Cookie,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.ai.client import (
    AIConfigurationError,
    OpenAIMatchExplainer,
)
from src.auth.session import SESSION_COOKIE_NAME
from src.database.auth_repository import AuthRepository
from src.database.bug_report_repository import (
    BugReportRepository,
)
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


def get_auth_repository(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> AuthRepository:
    return AuthRepository(
        session
    )


def get_bug_report_repository(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> BugReportRepository:
    return BugReportRepository(
        session
    )


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
    analysis_repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
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
        analysis_repository=analysis_repository,
        max_active_jobs=max_active_jobs,
    )


def get_match_ai_explainer() -> OpenAIMatchExplainer:
    try:
        return OpenAIMatchExplainer()
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI coach is not configured",
        ) from exc


def get_current_user(
    auth_repository: Annotated[
        AuthRepository,
        Depends(get_auth_repository),
    ],
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> CurrentUser:
    """
    Resolve the authenticated product user.

    Browser sessions are the primary identity source.

    The environment-backed identity remains available only
    behind an explicit development fallback switch.
    """
    if session_token:
        authenticated = (
            auth_repository.resolve_session(
                session_token
            )
        )

        if authenticated is not None:
            return CurrentUser(
                steam_id=authenticated.steam_id
            )

    allow_dev_fallback = (
        os.environ.get(
            "AUTH_DEV_IDENTITY_FALLBACK",
            "",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
        }
    )

    if allow_dev_fallback:
        steam_id = (
            os.environ.get(
                "CURRENT_USER_STEAM_ID",
                "",
            )
            .strip()
        )

        if steam_id:
            return CurrentUser(
                steam_id=steam_id
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
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

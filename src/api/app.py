from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.dependencies import (
    dispose_database_resources,
    get_analysis_job_repository,
    get_analysis_repository,
    get_database_session,
)
from src.api.schemas import (
    AnalysisJobResponse,
    HealthResponse,
    MatchAnalysisResponse,
    ReadyResponse,
)
from src.database.job_repository import AnalysisJobRepository
from src.database.repository import AnalysisRepository


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        dispose_database_resources()


app = FastAPI(
    title="CS2 Performance Lab API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(
    _: Request,
    __: SQLAlchemyError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database unavailable",
        },
    )


@app.get(
    "/health",
    response_model=HealthResponse,
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok"
    )


@app.get(
    "/ready",
    response_model=ReadyResponse,
)
def ready(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> ReadyResponse:
    session.execute(
        text("SELECT 1")
    )

    return ReadyResponse(
        status="ready"
    )


@app.get(
    "/analysis-jobs/{job_id}",
    response_model=AnalysisJobResponse,
)
def get_analysis_job(
    job_id: str,
    repository: Annotated[
        AnalysisJobRepository,
        Depends(get_analysis_job_repository),
    ],
) -> AnalysisJobResponse:
    job = repository.get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )

    return AnalysisJobResponse.model_validate(
        job
    )


@app.get(
    "/matches/{match_id}",
    response_model=MatchAnalysisResponse,
)
def get_match_analysis(
    match_id: str,
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
) -> MatchAnalysisResponse:
    analysis = repository.get_analysis(
        match_id
    )

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    return MatchAnalysisResponse.model_validate(
        analysis
    )

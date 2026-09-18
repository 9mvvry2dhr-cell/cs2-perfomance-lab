from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.dependencies import (
    dispose_database_resources,
    get_analysis_job_repository,
    get_analysis_repository,
    get_current_user,
    get_database_session,
    get_demo_ingestion_service,
)
from src.api.schemas import (
    AnalysisJobResponse,
    CurrentUserResponse,
    HealthResponse,
    MatchAnalysisResponse,
    PlayerHistorySummaryResponse,
    PlayerMatchHistoryResponse,
    ReadyResponse,
)
from src.database.job_repository import AnalysisJobRepository
from src.database.repository import AnalysisRepository
from src.domain.identity import CurrentUser
from src.ingestion.service import (
    AnalysisQueueFullError,
    DemoIngestionService,
)
from src.ingestion.storage import (
    DemoStorageFullError,
    DemoTooLargeError,
    InvalidDemoFileError,
)


FRONTEND_DIR = (
    Path(__file__).resolve().parents[2]
    / "frontend"
)


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


def require_owned_steam_id(
    requested_steam_id: str,
    current_user: CurrentUser,
) -> None:
    if (
        requested_steam_id
        != current_user.steam_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access to another player is forbidden"
            ),
        )


@app.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_me(
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        steam_id=current_user.steam_id
    )


@app.post(
    "/analysis-jobs",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_analysis_job(
    file: Annotated[
        UploadFile,
        File(...),
    ],
    service: Annotated[
        DemoIngestionService,
        Depends(get_demo_ingestion_service),
    ],
) -> AnalysisJobResponse:
    filename = file.filename or ""

    try:
        job = service.ingest(
            original_filename=filename,
            source=file.file,
        )

    except AnalysisQueueFullError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=str(exc),
            headers={
                "Retry-After": "30",
            },
        ) from exc

    except DemoStorageFullError as exc:
        raise HTTPException(
            status_code=507,
            detail=str(exc),
        ) from exc

    except DemoTooLargeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=str(exc),
        ) from exc

    except InvalidDemoFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AnalysisJobResponse.model_validate(
        job
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
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
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

    player = next(
        (
            item
            for item in analysis.players
            if item.steam_id
            == current_user.steam_id
        ),
        None,
    )

    if player is None:
        # Do not reveal whether another user's match exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    owned_analysis = replace(
        analysis,
        players=[
            player
        ],
    )

    return MatchAnalysisResponse.model_validate(
        owned_analysis
    )

@app.get(
    "/players/{steam_id}/matches",
    response_model=list[
        PlayerMatchHistoryResponse
    ],
)
def get_player_match_history(
    steam_id: str,
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
) -> list[PlayerMatchHistoryResponse]:
    require_owned_steam_id(
        steam_id,
        current_user,
    )

    history = (
        repository
        .get_player_match_history(
            steam_id,
            limit=limit,
        )
    )

    return [
        PlayerMatchHistoryResponse
        .model_validate(item)
        for item in history
    ]


@app.get(
    "/players/{steam_id}/summary",
    response_model=PlayerHistorySummaryResponse,
)
def get_player_history_summary(
    steam_id: str,
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 10,
) -> PlayerHistorySummaryResponse:
    require_owned_steam_id(
        steam_id,
        current_user,
    )

    summary = (
        repository
        .get_player_history_summary(
            steam_id,
            limit=limit,
        )
    )

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player history not found",
        )

    return (
        PlayerHistorySummaryResponse
        .model_validate(summary)
    )


@app.get(
    "/me/matches",
    response_model=list[
        PlayerMatchHistoryResponse
    ],
)
def get_my_match_history(
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
) -> list[PlayerMatchHistoryResponse]:
    history = repository.get_player_match_history(
        current_user.steam_id,
        limit=limit,
    )

    return [
        PlayerMatchHistoryResponse
        .model_validate(item)
        for item in history
    ]


@app.get(
    "/me/summary",
    response_model=PlayerHistorySummaryResponse,
)
def get_my_history_summary(
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 10,
) -> PlayerHistorySummaryResponse:
    summary = repository.get_player_history_summary(
        current_user.steam_id,
        limit=limit,
    )

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player history not found",
        )

    return (
        PlayerHistorySummaryResponse
        .model_validate(summary)
    )


# Frontend is mounted last so API routes keep priority.
app.mount(
    "/",
    StaticFiles(
        directory=str(FRONTEND_DIR),
        html=True,
    ),
    name="frontend",
)

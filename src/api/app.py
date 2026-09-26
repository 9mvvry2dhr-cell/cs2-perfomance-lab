from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import os
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
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.ai.client import (
    AIProviderError,
    AIResponseValidationError,
    OpenAIMatchExplainer,
    OpenAIPlayerExplainer,
)
from src.ai.models import (
    MatchAIResponse,
    PlayerAIResponse,
)
from src.ai.payload import (
    build_match_ai_payload,
    build_player_ai_payload,
)
from src.auth.steam_openid import (
    SteamOpenIDError,
    build_steam_login_url,
    verify_steam_openid_response,
)
from src.auth.session import SESSION_COOKIE_NAME
from src.auth.steam_profile import fetch_steam_profile
from src.api.dependencies import (
    dispose_database_resources,
    get_auth_repository,
    get_bug_report_repository,
    get_analysis_job_repository,
    get_analysis_repository,
    get_current_user,
    get_database_session,
    get_demo_ingestion_service,
    get_match_ai_explainer,
    get_player_ai_explainer,
)
from src.api.schemas import (
    AnalysisJobResponse,
    BugReportCreateRequest,
    BugReportResponse,
    CurrentUserResponse,
    HealthResponse,
    MatchAnalysisResponse,
    PlayerHistorySummaryResponse,
    PlayerMatchHistoryResponse,
    ReadyResponse,
)
from src.database.auth_repository import (
    AuthRepository,
    DEFAULT_SESSION_LIFETIME,
)
from src.database.bug_report_repository import (
    BugReportRateLimitError,
    BugReportReferenceError,
    BugReportRepository,
)
from src.database.job_repository import AnalysisJobRepository
from src.database.repository import AnalysisRepository
from src.domain.history import (
    build_player_history_summary,
)
from src.domain.identity import CurrentUser
from src.ingestion.service import (
    AnalysisQueueFullError,
    DemoIngestionService,
    DuplicateDemoError,
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


@app.get(
    "/auth/steam/login",
)
def steam_login(
    request: Request,
) -> RedirectResponse:
    base_url = str(
        request.base_url
    ).rstrip("/")

    login_url = build_steam_login_url(
        return_to=(
            f"{base_url}"
            "/auth/steam/callback"
        ),
        realm=base_url,
    )

    return RedirectResponse(
        url=login_url,
        status_code=307,
    )


@app.get(
    "/auth/steam/callback",
)
def steam_callback(
    request: Request,
    auth_repository: Annotated[
        AuthRepository,
        Depends(get_auth_repository),
    ],
) -> RedirectResponse:
    params = dict(
        request.query_params
    )

    try:
        steam_id = (
            verify_steam_openid_response(
                params
            )
        )
    except SteamOpenIDError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Steam authentication failed",
        ) from exc

    created = auth_repository.create_session(
        steam_id
    )

    response = RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=created.token,
        max_age=int(
            DEFAULT_SESSION_LIFETIME.total_seconds()
        ),
        httponly=True,
        secure=(
            request.url.scheme == "https"
        ),
        samesite="lax",
        path="/",
    )

    return response


@app.post(
    "/auth/logout",
)
def logout(
    request: Request,
    auth_repository: Annotated[
        AuthRepository,
        Depends(get_auth_repository),
    ],
) -> RedirectResponse:
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if token:
        auth_repository.revoke_session(
            token
        )

    response = RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return response


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


def _get_current_steam_player_name(
    current_user: CurrentUser,
) -> str | None:
    api_key = os.getenv(
        "STEAM_API_KEY",
        "",
    ).strip()

    profile = fetch_steam_profile(
        steam_id=current_user.steam_id,
        api_key=api_key,
    )

    if profile is None:
        return None

    return profile.player_name


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
    api_key = os.getenv(
        "STEAM_API_KEY",
        "",
    ).strip()

    profile = fetch_steam_profile(
        steam_id=current_user.steam_id,
        api_key=api_key,
    )

    return CurrentUserResponse(
        steam_id=current_user.steam_id,
        player_name=(
            profile.player_name
            if profile
            else None
        ),
        avatar_url=(
            profile.avatar_url
            if profile
            else None
        ),
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
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> AnalysisJobResponse:
    filename = file.filename or ""

    try:
        job = service.ingest(
            owner_steam_id=current_user.steam_id,
            original_filename=filename,
            source=file.file,
        )

    except DuplicateDemoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

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
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> AnalysisJobResponse:
    job = repository.get_owned_job(
        job_id,
        owner_steam_id=current_user.steam_id,
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
    player_position = (
        repository.get_user_match_position(
            owner_steam_id=current_user.steam_id,
            match_id=match_id,
        )
    )

    if player_position is None:
        # Do not reveal whether another user's match exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    analysis = repository.get_analysis(
        match_id
    )

    if (
        analysis is None
        or player_position < 0
        or player_position >= len(analysis.players)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    player = analysis.players[
        player_position
    ]

    steam_player_name = (
        _get_current_steam_player_name(
            current_user
        )
    )

    public_player = replace(
        player,
        steam_id=current_user.steam_id,
        name=(
            steam_player_name
            or player.name
        ),
    )

    owned_analysis = replace(
        analysis,
        players=[
            public_player
        ],
    )

    return MatchAnalysisResponse.model_validate(
        owned_analysis
    )

@app.post(
    "/matches/{match_id}/ai-explanation",
    response_model=MatchAIResponse,
)
def explain_match_with_ai(
    match_id: str,
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    explainer: Annotated[
        OpenAIMatchExplainer,
        Depends(get_match_ai_explainer),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> MatchAIResponse:
    player_position = (
        repository.get_user_match_position(
            owner_steam_id=current_user.steam_id,
            match_id=match_id,
        )
    )

    if player_position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    analysis = repository.get_analysis(
        match_id
    )

    if (
        analysis is None
        or player_position < 0
        or player_position >= len(analysis.players)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    player = analysis.players[
        player_position
    ]

    payload = build_match_ai_payload(
        analysis,
        steam_id=player.steam_id,
    )

    try:
        return explainer.explain_with_usage(
            payload
        )
    except AIResponseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI response failed evidence validation",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider request failed",
        ) from exc


@app.post(
    "/me/ai-overview",
    response_model=PlayerAIResponse,
)
def explain_player_with_ai(
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    explainer: Annotated[
        OpenAIPlayerExplainer,
        Depends(get_player_ai_explainer),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> PlayerAIResponse:
    history = (
        repository
        .get_player_match_history(
            current_user.steam_id,
            limit=100,
            owner_steam_id=(
                current_user.steam_id
            ),
        )
    )

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player history not found",
        )

    summary = build_player_history_summary(
        current_user.steam_id,
        history,
    )

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player history not found",
        )

    payload = build_player_ai_payload(
        summary,
        history,
    )

    try:
        return explainer.explain_with_usage(
            payload
        )
    except AIResponseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI response failed evidence validation",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider request failed",
        ) from exc


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
            owner_steam_id=(
                current_user.steam_id
            ),
        )
    )

    steam_player_name = (
        _get_current_steam_player_name(
            current_user
        )
    )

    return [
        PlayerMatchHistoryResponse
        .model_validate(
            replace(
                item,
                player_name=(
                    steam_player_name
                    or item.player_name
                ),
            )
        )
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
            owner_steam_id=(
                current_user.steam_id
            ),
        )
    )

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player history not found",
        )

    steam_player_name = (
        _get_current_steam_player_name(
            current_user
        )
    )

    public_summary = replace(
        summary,
        steam_id=current_user.steam_id,
        player_name=(
            steam_player_name
            or summary.player_name
        ),
    )

    return (
        PlayerHistorySummaryResponse
        .model_validate(public_summary)
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
        owner_steam_id=current_user.steam_id,
    )

    steam_player_name = (
        _get_current_steam_player_name(
            current_user
        )
    )

    return [
        PlayerMatchHistoryResponse
        .model_validate(
            replace(
                item,
                player_name=(
                    steam_player_name
                    or item.player_name
                ),
            )
        )
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
        owner_steam_id=current_user.steam_id,
    )

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player history not found",
        )

    steam_player_name = (
        _get_current_steam_player_name(
            current_user
        )
    )

    public_summary = replace(
        summary,
        steam_id=current_user.steam_id,
        player_name=(
            steam_player_name
            or summary.player_name
        ),
    )

    return (
        PlayerHistorySummaryResponse
        .model_validate(public_summary)
    )


@app.post(
    "/bug-reports",
    response_model=BugReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bug_report(
    payload: BugReportCreateRequest,
    repository: Annotated[
        BugReportRepository,
        Depends(get_bug_report_repository),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> BugReportResponse:
    try:
        report = repository.create_report(
            owner_steam_id=(
                current_user.steam_id
            ),
            category=payload.category,
            message=payload.message,
            match_id=payload.match_id,
            job_id=payload.job_id,
        )

    except BugReportRateLimitError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Слишком много сообщений "
                "об ошибках. Попробуй позже."
            ),
            headers={
                "Retry-After": str(
                    exc.retry_after_seconds
                ),
            },
        ) from exc

    except BugReportReferenceError as exc:
        # Do not reveal whether another user's
        # match/job actually exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Referenced match or "
                "analysis job not found"
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return BugReportResponse.model_validate(
        report
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

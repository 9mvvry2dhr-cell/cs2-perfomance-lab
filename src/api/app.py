from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import os
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
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
from src.audit import audit_event
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
    get_ai_overview_quota_repository,
    get_analysis_job_repository,
    get_analysis_repository,
    get_current_user,
    get_database_session,
    get_demo_ingestion_service,
    get_match_ai_explainer,
    get_match_ai_report_repository,
    get_player_ai_explainer,
    get_presence_repository,
)
from src.api.schemas import (
    AIOverviewQuotaResponse,
    AnalysisJobResponse,
    BugReportCreateRequest,
    BugReportResponse,
    CurrentUserResponse,
    FoundingTesterAdminItem,
    FoundingTesterAdminResponse,
    FoundingTesterSummaryResponse,
    HealthResponse,
    MatchAnalysisResponse,
    PlayerHistorySummaryResponse,
    PlayerMatchHistoryResponse,
    PresenceHeartbeatRequest,
    PresenceSummaryResponse,
    ReadyResponse,
)
from src.database.ai_overview_quota_repository import (
    AIOverviewRateLimitError,
    AIOverviewQuotaRepository,
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
from src.database.models import FoundingTesterModel
from src.database.match_ai_report_repository import (
    MatchAIReportRepository,
)
from src.database.repository import AnalysisRepository
from src.database.presence_repository import (
    PresenceRepository,
)
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
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


_SAFE_HTTP_METHODS = frozenset(
    {
        "GET",
        "HEAD",
        "OPTIONS",
    }
)


def _ai_coach_enabled() -> bool:
    return (
        os.environ.get(
            "AI_COACH_ENABLED",
            "true",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def _require_ai_coach_enabled() -> None:
    if _ai_coach_enabled():
        return

    raise HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        detail=(
            "AI coach is temporarily disabled"
        ),
    )


def _default_port(
    scheme: str,
) -> int | None:
    if scheme == "https":
        return 443

    if scheme == "http":
        return 80

    return None


def _request_is_cross_site_mutation(
    request: Request,
) -> bool:
    if (
        request.method.upper()
        in _SAFE_HTTP_METHODS
    ):
        return False

    fetch_site = (
        request.headers
        .get(
            "sec-fetch-site",
            "",
        )
        .strip()
        .lower()
    )

    if fetch_site == "cross-site":
        return True

    origin = (
        request.headers
        .get(
            "origin",
            "",
        )
        .strip()
    )

    if not origin:
        return False

    try:
        parsed = urlsplit(
            origin
        )

        origin_scheme = (
            parsed.scheme.lower()
        )

        origin_host = (
            parsed.hostname
            or ""
        ).lower()

        origin_port = (
            parsed.port
            or _default_port(
                origin_scheme
            )
        )

        request_scheme = (
            request.url.scheme
            .lower()
        )

        request_host = (
            request.url.hostname
            or ""
        ).lower()

        request_port = (
            request.url.port
            or _default_port(
                request_scheme
            )
        )

    except ValueError:
        return True

    return (
        not origin_scheme
        or not origin_host
        or origin_scheme
        != request_scheme
        or origin_host
        != request_host
        or origin_port
        != request_port
    )


@app.middleware("http")
async def block_cross_site_mutations(
    request: Request,
    call_next,
):
    if _request_is_cross_site_mutation(
        request
    ):
        audit_event(
            "security.cross_site_blocked",
            status="blocked",
            method=request.method,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            content={
                "detail": (
                    "Cross-site request blocked"
                ),
            },
        )

    return await call_next(
        request
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


@app.post(
    "/presence/heartbeat",
    response_model=PresenceSummaryResponse,
)
def presence_heartbeat(
    payload: PresenceHeartbeatRequest,
    request: Request,
    presence_repository: Annotated[
        PresenceRepository,
        Depends(get_presence_repository),
    ],
    auth_repository: Annotated[
        AuthRepository,
        Depends(get_auth_repository),
    ],
) -> PresenceSummaryResponse:
    presence_repository.touch(
        str(payload.visitor_id)
    )

    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if token:
        auth_repository.resolve_session(
            token
        )

    summary = (
        presence_repository.get_summary()
    )

    return PresenceSummaryResponse(
        online=summary.online,
        visitors_24h=summary.visitors_24h,
        logged_in_online=(
            summary.logged_in_online
        ),
    )


@app.get(
    "/presence/summary",
    response_model=PresenceSummaryResponse,
)
def presence_summary(
    presence_repository: Annotated[
        PresenceRepository,
        Depends(get_presence_repository),
    ],
) -> PresenceSummaryResponse:
    summary = (
        presence_repository.get_summary()
    )

    return PresenceSummaryResponse(
        online=summary.online,
        visitors_24h=summary.visitors_24h,
        logged_in_online=(
            summary.logged_in_online
        ),
    )


@app.get(
    "/founding-testers/summary",
    response_model=FoundingTesterSummaryResponse,
)
def founding_testers_summary(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> FoundingTesterSummaryResponse:
    total = int(
        session.scalar(
            select(
                func.count()
            ).select_from(
                FoundingTesterModel
            )
        )
        or 0
    )

    claimed = int(
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                FoundingTesterModel
            )
            .where(
                FoundingTesterModel.steam_id
                .is_not(None)
            )
        )
        or 0
    )

    return FoundingTesterSummaryResponse(
        total=total,
        claimed=claimed,
        remaining=max(
            total - claimed,
            0,
        ),
    )


@app.get(
    "/admin/founding-testers",
    response_model=FoundingTesterAdminResponse,
)
def admin_founding_testers(
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> FoundingTesterAdminResponse:
    admin_steam_id = (
        os.environ.get(
            "ADMIN_STEAM_ID",
            "",
        )
        .strip()
    )

    if not admin_steam_id:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Admin access is not configured",
        )

    if current_user.steam_id != admin_steam_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    rows = list(
        session.scalars(
            select(
                FoundingTesterModel
            )
            .where(
                FoundingTesterModel.steam_id
                .is_not(None)
            )
            .order_by(
                FoundingTesterModel.number
            )
        )
    )

    total = int(
        session.scalar(
            select(
                func.count()
            ).select_from(
                FoundingTesterModel
            )
        )
        or 0
    )

    claimed = len(rows)

    return FoundingTesterAdminResponse(
        total=total,
        claimed=claimed,
        remaining=max(
            total - claimed,
            0,
        ),
        testers=[
            FoundingTesterAdminItem(
                number=row.number,
                steam_id=row.steam_id,
                awarded_at=row.awarded_at,
                premium_days=row.premium_days,
            )
            for row in rows
            if (
                row.steam_id is not None
                and row.awarded_at is not None
            )
        ],
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

    audit_event(
        "auth.login",
        steam_id=steam_id,
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

    steam_id = None

    if token:
        authenticated = (
            auth_repository.resolve_session(
                token
            )
        )

        if authenticated is not None:
            steam_id = authenticated.steam_id

        auth_repository.revoke_session(
            token
        )

    if steam_id is not None:
        audit_event(
            "auth.logout",
            steam_id=steam_id,
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
    session: Annotated[
        Session,
        Depends(get_database_session),
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

    founding_tester_number = (
        session.scalar(
            select(
                FoundingTesterModel.number
            ).where(
                FoundingTesterModel.steam_id
                == current_user.steam_id
            )
        )
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
        founding_tester_number=(
            founding_tester_number
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
    match_source: Annotated[
        Literal[
            "premier",
            "faceit",
            "unknown",
        ],
        Form(),
    ] = "unknown",
) -> AnalysisJobResponse:
    filename = file.filename or ""

    try:
        job = service.ingest(
            owner_steam_id=current_user.steam_id,
            original_filename=filename,
            source=file.file,
            match_source=match_source,
        )

        audit_event(
            "demo.upload.accepted",
            steam_id=current_user.steam_id,
            job_id=job.id,
            match_source=job.match_source,
        )

    except DuplicateDemoError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "match_id": exc.match_id,
            },
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

    response = (
        AnalysisJobResponse.model_validate(
            job
        )
    )

    if job.status != "queued":
        return response

    return response.model_copy(
        update={
            "jobs_ahead": (
                repository.count_jobs_ahead(
                    job_id
                )
            ),
        }
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

    response = MatchAnalysisResponse.model_validate(
        owned_analysis
    )

    return response.model_copy(
        update={
            "focus_player_ref": (
                f"anon:{player_position}"
            ),
        }
    )


# Public read-only showcase generated from one real verified match.
# It exposes only one anonymized player and does not require Steam auth.
_DEMO_ANALYSIS_MATCH_ID = (
    "4016d7df54312b596014941979f22711"
    "048eb8905beb54914c178e6f4be018f7"
)
_DEMO_ANALYSIS_PLAYER_POSITION = 4


@app.get(
    "/demo-analysis",
    response_model=MatchAnalysisResponse,
)
def get_demo_analysis(
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
) -> MatchAnalysisResponse:
    analysis = repository.get_analysis(
        _DEMO_ANALYSIS_MATCH_ID
    )

    if (
        analysis is None
        or not analysis.is_valid
        or _DEMO_ANALYSIS_PLAYER_POSITION < 0
        or _DEMO_ANALYSIS_PLAYER_POSITION >= len(analysis.players)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo analysis not available",
        )

    player = analysis.players[
        _DEMO_ANALYSIS_PLAYER_POSITION
    ]

    demo_player = replace(
        player,
        steam_id="demo",
        name="Demo Player",
    )

    demo_analysis = replace(
        analysis,
        match_id="demo-showcase",
        players=[
            demo_player
        ],
    )

    response = MatchAnalysisResponse.model_validate(
        demo_analysis
    )

    return response.model_copy(
        update={
            "focus_player_ref": (
                f"anon:{_DEMO_ANALYSIS_PLAYER_POSITION}"
            ),
        }
    )


@app.get(
    "/matches/{match_id}/ai-explanation/latest",
    response_model=MatchAIResponse,
)
def get_latest_match_ai_explanation(
    match_id: str,
    report_repository: Annotated[
        MatchAIReportRepository,
        Depends(
            get_match_ai_report_repository
        ),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> MatchAIResponse:
    cached = (
        report_repository
        .get_cached_response(
            owner_steam_id=(
                current_user.steam_id
            ),
            match_id=match_id,
        )
    )

    if cached is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI match explanation not found",
        )

    return MatchAIResponse.model_validate(
        cached
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
    report_repository: Annotated[
        MatchAIReportRepository,
        Depends(
            get_match_ai_report_repository
        ),
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
    _require_ai_coach_enabled()

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

    cached = (
        report_repository
        .reserve_generation(
            owner_steam_id=(
                current_user.steam_id
            ),
            match_id=match_id,
        )
    )

    if cached is not None:
        audit_event(
            "ai.match.cached",
            steam_id=current_user.steam_id,
            match_id=match_id,
        )

        return MatchAIResponse.model_validate(
            cached
        )

    try:
        result = explainer.explain_with_usage(
            payload
        )

        report_repository.commit_success(
            result.model_dump(
                mode="json"
            )
        )

        audit_event(
            "ai.match.generated",
            steam_id=current_user.steam_id,
            match_id=match_id,
            input_tokens=(
                result.usage.input_tokens
            ),
            output_tokens=(
                result.usage.output_tokens
            ),
            reasoning_tokens=(
                result.usage.reasoning_tokens
            ),
            total_tokens=(
                result.usage.total_tokens
            ),
        )

        return result

    except AIResponseValidationError as exc:
        report_repository.cancel_generation()

        audit_event(
            "ai.match.failed",
            steam_id=current_user.steam_id,
            status="failed",
            match_id=match_id,
            reason="evidence_validation",
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI response failed evidence validation",
        ) from exc

    except AIProviderError as exc:
        report_repository.cancel_generation()

        audit_event(
            "ai.match.failed",
            steam_id=current_user.steam_id,
            status="failed",
            match_id=match_id,
            reason="provider",
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider request failed",
        ) from exc

    except Exception:
        report_repository.cancel_generation()

        audit_event(
            "ai.match.failed",
            steam_id=current_user.steam_id,
            status="failed",
            match_id=match_id,
            reason="internal",
        )

        raise


@app.get(
    "/me/ai-overview/status",
    response_model=AIOverviewQuotaResponse,
)
def get_ai_overview_status(
    quota_repository: Annotated[
        AIOverviewQuotaRepository,
        Depends(
            get_ai_overview_quota_repository
        ),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> AIOverviewQuotaResponse:
    quota = quota_repository.get_status(
        current_user.steam_id
    )

    return AIOverviewQuotaResponse(
        available=quota.available,
        cooldown_days=(
            quota.cooldown_days
        ),
        last_generated_at=(
            quota.last_generated_at
        ),
        next_available_at=(
            quota.next_available_at
        ),
        has_cached_report=(
            quota.has_cached_report
        ),
    )


@app.get(
    "/me/ai-overview/latest",
    response_model=PlayerAIResponse,
)
def get_latest_ai_overview(
    quota_repository: Annotated[
        AIOverviewQuotaRepository,
        Depends(
            get_ai_overview_quota_repository
        ),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> PlayerAIResponse:
    cached = (
        quota_repository
        .get_cached_response(
            current_user.steam_id
        )
    )

    if cached is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI overview not found",
        )

    return PlayerAIResponse.model_validate(
        cached
    )


@app.post(
    "/me/ai-overview",
    response_model=PlayerAIResponse,
)
def explain_player_with_ai(
    repository: Annotated[
        AnalysisRepository,
        Depends(get_analysis_repository),
    ],
    quota_repository: Annotated[
        AIOverviewQuotaRepository,
        Depends(
            get_ai_overview_quota_repository
        ),
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
    _require_ai_coach_enabled()

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
        quota_repository.reserve_generation(
            current_user.steam_id
        )
    except AIOverviewRateLimitError as exc:
        audit_event(
            "ai.overview.rate_limited",
            steam_id=current_user.steam_id,
            status="failed",
        )

        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Общий разбор доступен раз в "
                "30 дней. Следующий запуск: "
                + exc.next_available_at.isoformat()
            ),
            headers={
                "Retry-After": str(
                    exc.retry_after_seconds
                ),
            },
        ) from exc

    try:
        result = explainer.explain_with_usage(
            payload
        )

        quota_repository.commit_success(
            result.model_dump(
                mode="json"
            )
        )

        audit_event(
            "ai.overview.generated",
            steam_id=current_user.steam_id,
            matches=len(history),
            input_tokens=(
                result.usage.input_tokens
            ),
            output_tokens=(
                result.usage.output_tokens
            ),
            reasoning_tokens=(
                result.usage.reasoning_tokens
            ),
            total_tokens=(
                result.usage.total_tokens
            ),
        )

        return result

    except AIResponseValidationError as exc:
        quota_repository.cancel_generation()

        audit_event(
            "ai.overview.failed",
            steam_id=current_user.steam_id,
            status="failed",
            reason="evidence_validation",
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI response failed evidence validation",
        ) from exc

    except AIProviderError as exc:
        quota_repository.cancel_generation()

        audit_event(
            "ai.overview.failed",
            steam_id=current_user.steam_id,
            status="failed",
            reason="provider",
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider request failed",
        ) from exc

    except Exception:
        quota_repository.cancel_generation()

        audit_event(
            "ai.overview.failed",
            steam_id=current_user.steam_id,
            status="failed",
            reason="internal",
        )

        raise


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
    source: Annotated[
        Literal[
            "premier",
            "faceit",
            "unknown",
        ] | None,
        Query(),
    ] = None,
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
            match_source=source,
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
    source: Annotated[
        Literal[
            "premier",
            "faceit",
            "unknown",
        ] | None,
        Query(),
    ] = None,
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
            match_source=source,
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
    source: Annotated[
        Literal[
            "premier",
            "faceit",
            "unknown",
        ] | None,
        Query(),
    ] = None,
) -> list[PlayerMatchHistoryResponse]:
    history = repository.get_player_match_history(
        current_user.steam_id,
        limit=limit,
        owner_steam_id=current_user.steam_id,
        match_source=source,
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
    source: Annotated[
        Literal[
            "premier",
            "faceit",
            "unknown",
        ] | None,
        Query(),
    ] = None,
) -> PlayerHistorySummaryResponse:
    summary = repository.get_player_history_summary(
        current_user.steam_id,
        limit=limit,
        owner_steam_id=current_user.steam_id,
        match_source=source,
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

    audit_event(
        "bug_report.created",
        steam_id=current_user.steam_id,
        category=report.category,
        match_id=report.match_id,
        job_id=report.job_id,
    )

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

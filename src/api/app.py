from __future__ import annotations

from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    status,
)

from src.api.dependencies import (
    get_analysis_repository,
)
from src.api.schemas import (
    HealthResponse,
    MatchAnalysisResponse,
)
from src.database.repository import (
    AnalysisRepository,
)


app = FastAPI(
    title="CS2 Performance Lab API",
    version="0.1.0",
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

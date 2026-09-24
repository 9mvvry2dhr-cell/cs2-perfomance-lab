from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )


class CurrentUserResponse(ApiModel):
    steam_id: str
    player_name: str | None = None
    avatar_url: str | None = None


class HealthResponse(ApiModel):
    status: Literal["ok"]


class ReadyResponse(ApiModel):
    status: Literal["ready"]


class AnalysisJobResponse(ApiModel):
    id: str
    status: Literal[
        "queued",
        "processing",
        "completed",
        "failed",
    ]
    original_filename: str

    match_id: str | None
    error: str | None

    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class BugReportCreateRequest(ApiModel):
    category: Literal[
        "analysis",
        "statistics",
        "ai",
        "ui",
        "other",
    ]

    message: str = Field(
        min_length=5,
        max_length=3000,
    )

    match_id: str | None = None
    job_id: str | None = None


class BugReportResponse(ApiModel):
    id: str

    category: Literal[
        "analysis",
        "statistics",
        "ai",
        "ui",
        "other",
    ]

    message: str
    match_id: str | None
    job_id: str | None
    created_at: datetime


class FindingResponse(ApiModel):
    code: str
    category: str
    kind: Literal["strength", "weakness"]
    severity: Literal["low", "medium", "high"]
    side: str
    evidence: dict[str, float]


class SideStatsResponse(ApiModel):
    rounds_played: int
    kills: int
    deaths: int
    damage: float
    adr: float

    kast_rounds: int
    kast_pct: float

    survived_rounds: int
    survival_pct: float

    entry_kills: int
    entry_deaths: int


class PlayerStatsResponse(ApiModel):
    rounds_played: int
    kills: int
    deaths: int
    assists: int
    headshots: int
    damage: float

    kd: float
    adr: float
    headshot_pct: float

    kast_rounds: int
    kast_pct: float

    survived_rounds: int
    survival_pct: float

    entry_kills: int
    entry_deaths: int

    he_damage: float
    inferno_damage: float
    enemies_flashed: int
    flash_duration: float

    clutches_won: int
    trade_kills: int
    traded_deaths: int

    two_k_rounds: int
    three_k_rounds: int
    four_k_rounds: int
    five_k_rounds: int


class PlayerAnalysisResponse(ApiModel):
    steam_id: str
    name: str
    stats: PlayerStatsResponse
    sides: dict[str, SideStatsResponse]
    findings: list[FindingResponse]


class PlayerMatchHistoryResponse(ApiModel):
    match_id: str
    analyzed_at: datetime

    map_name: str
    score_ct: int
    score_t: int

    player_name: str
    stats: PlayerStatsResponse
    findings: list[FindingResponse]

    player_result: Literal[
        "win",
        "loss",
        "draw",
        "unknown",
    ] = "unknown"


class PlayerFindingFrequencyResponse(ApiModel):
    code: str
    category: str
    kind: Literal[
        "strength",
        "weakness",
    ]

    matches: int
    match_rate_pct: float


class PlayerHistorySummaryResponse(ApiModel):
    steam_id: str
    player_name: str

    matches_analyzed: int
    stats: PlayerStatsResponse

    finding_frequency: list[
        PlayerFindingFrequencyResponse
    ]


class MatchAnalysisResponse(ApiModel):
    match_id: str
    map_name: str
    duration_seconds: int
    rounds_played: int

    score_ct: int
    score_t: int
    winner_side: str

    is_valid: bool
    validation_error: str | None

    players: list[PlayerAnalysisResponse]

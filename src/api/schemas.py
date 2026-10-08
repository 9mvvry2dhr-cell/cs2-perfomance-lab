from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )


class CurrentUserResponse(ApiModel):
    steam_id: str
    player_name: str | None = None
    avatar_url: str | None = None
    founding_tester_number: int | None = None


class HealthResponse(ApiModel):
    status: Literal["ok"]


class ReadyResponse(ApiModel):
    status: Literal["ready"]


class PresenceHeartbeatRequest(ApiModel):
    visitor_id: UUID


class PresenceSummaryResponse(ApiModel):
    online: int
    visitors_24h: int
    logged_in_online: int


class FoundingTesterSummaryResponse(ApiModel):
    total: int
    claimed: int
    remaining: int


class FoundingTesterAdminItem(ApiModel):
    number: int
    steam_id: str
    awarded_at: datetime
    premium_days: int


class FoundingTesterAdminResponse(ApiModel):
    total: int
    claimed: int
    remaining: int
    testers: list[FoundingTesterAdminItem]


class AIOverviewQuotaResponse(ApiModel):
    available: bool
    cooldown_days: int
    last_generated_at: datetime | None = None
    next_available_at: datetime | None = None
    has_cached_report: bool


class AnalysisJobResponse(ApiModel):
    id: str
    status: Literal[
        "queued",
        "processing",
        "completed",
        "failed",
    ]
    original_filename: str
    match_source: Literal[
        "premier",
        "faceit",
        "unknown",
    ] = "unknown"

    match_id: str | None
    error: str | None

    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    jobs_ahead: int | None = None


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

    clutch_attempts: int | None = None
    trade_opportunities: int | None = None


class MatchStoryEventResponse(ApiModel):
    round_num: int
    event_type: Literal[
        "highlight",
        "growth",
        "key",
    ]
    score: float
    evidence: dict[
        str,
        int | float | bool,
    ]


class GrowthSignalResponse(ApiModel):
    code: str

    kind: Literal[
        "growth",
        "strength",
        "neutral",
        "insufficient",
    ]

    confidence: Literal[
        "none",
        "low",
        "medium",
        "high",
    ]

    evidence: dict[
        str,
        int | float | None,
    ]


class PlayerAnalysisResponse(ApiModel):
    steam_id: str
    name: str
    stats: PlayerStatsResponse
    sides: dict[str, SideStatsResponse]
    findings: list[FindingResponse]

    growth_signals: list[
        GrowthSignalResponse
    ] = Field(
        default_factory=list
    )
    match_story: list[
        MatchStoryEventResponse
    ] = Field(
        default_factory=list
    )


class PlayerMatchHistoryResponse(ApiModel):
    match_id: str
    analyzed_at: datetime

    map_name: str
    score_ct: int
    score_t: int

    player_name: str
    stats: PlayerStatsResponse
    findings: list[FindingResponse]
    sides: dict[str, SideStatsResponse] = Field(
        default_factory=dict
    )

    player_result: Literal[
        "win",
        "loss",
        "draw",
        "unknown",
    ] = "unknown"

    match_source: Literal[
        "premier",
        "faceit",
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


class MatchFlowResponse(ApiModel):
    round_num: int

    winner_team: Literal[
        "team_a",
        "team_b",
    ]

    winner_side: Literal[
        "T",
        "CT",
    ]

    score_a_before: int
    score_b_before: int
    score_a_after: int
    score_b_after: int


class TurningRoundResponse(ApiModel):
    round_num: int

    winner_team: Literal[
        "team_a",
        "team_b",
    ]

    swing_type: Literal[
        "no_advantage",
        "clean_conversion",
        "regained",
        "comeback",
        "stolen",
        "swing",
    ]

    score_a_before: int
    score_b_before: int
    score_a_after: int
    score_b_after: int

    opponent_streak_before: int
    winner_run_length: int

    reasons: list[str]


class TurningControlEventResponse(ApiModel):
    round_num: int
    tick: int

    round_state_position: int

    event_type: Literal[
        "control_gain",
        "control_loss",
        "reversal",
        "equalizer",
    ]

    decisive: bool

    attacker: str | None
    victim: str | None

    attacker_team: int | None
    victim_team: int

    cause: str

    state_before: str
    state_after: str

    winner_advantage_before: int
    winner_advantage_after: int


class TurningRoundStoryResponse(ApiModel):
    round_num: int
    winner_team_num: int

    events: list[
        TurningControlEventResponse
    ]

    decisive_tick: int | None

    resolution: Literal[
        "sustained_control",
        "final_elimination",
        "unresolved",
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

    # Anonymous reference of the player this response
    # is focused on, for example "anon:3".
    # Used by the frontend to render "you" without
    # exposing demo Steam IDs inside match events.
    focus_player_ref: str | None = None

    match_flow: list[
        MatchFlowResponse
    ] = Field(
        default_factory=list
    )

    turning_rounds: list[
        TurningRoundResponse
    ] = Field(
        default_factory=list
    )

    turning_stories: list[
        TurningRoundStoryResponse
    ] = Field(
        default_factory=list
    )

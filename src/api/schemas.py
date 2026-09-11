from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )


class HealthResponse(ApiModel):
    status: Literal["ok"]


class ReadyResponse(ApiModel):
    status: Literal["ready"]


class FindingResponse(ApiModel):
    code: str
    category: str
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

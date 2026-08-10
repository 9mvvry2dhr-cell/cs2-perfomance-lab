from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class PlayerStats:
    """Статистика конкретного игрока за один матч."""
    steam_id: str
    name: str
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    damage: int = 0
    headshots: int = 0
    rounds_played: int = 0
    first_kills: int = 0
    first_deaths: int = 0
    flash_assists: int = 0
    utility_damage: int = 0

    @property
    def kd_ratio(self) -> float:
        """Расчёт соотношения убийств к смертям (K/D)."""
        if self.deaths == 0:
            return float(self.kills)
        return round(self.kills / self.deaths, 2)

    @property
    def adr(self) -> float:
        """Расчёт среднего урона за раунд (ADR)."""
        if self.rounds_played == 0:
            return 0.0
        return round(self.damage / self.rounds_played, 1)

    @property
    def hs_percentage(self) -> float:
        """Процент попаданий в голову (% HS)."""
        if self.kills == 0:
            return 0.0
        return round((self.headshots / self.kills) * 100, 1)


@dataclass
class Match:
    """Модель сыгранного матча CS2."""
    match_id: str
    map_name: str
    played_at: datetime
    duration_seconds: int = 0
    score_ct: int = 0
    score_t: int = 0
    winner_side: str = ""  # "CT" или "T"
    players: List[PlayerStats] = field(default_factory=list)

    @property
    def total_rounds(self) -> int:
        return self.score_ct + self.score_t


@dataclass
class PerformanceInsight:
    """Единица рекомендаций / анализа формы от AI Coach."""
    category: str  # Aim, Utility, Positioning, Entry и т.д.
    title: str
    description: str
    insight_type: str = "info"  # "positive", "warning", "info"
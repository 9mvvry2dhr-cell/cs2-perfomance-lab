from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedPlayer:
    steam_id: str
    name: str
    kills: int
    deaths: int
    assists: int
    damage: float
    headshots: int
    rounds_played: int

    @property
    def adr(self) -> float:
        if self.rounds_played <= 0:
            return 0.0
        return round(self.damage / self.rounds_played, 1)

    @property
    def hs_percent(self) -> float:
        if self.kills <= 0:
            return 0.0
        return round((self.headshots / self.kills) * 100, 1)


@dataclass
class ParsedMatch:
    match_id: str
    map_name: str
    duration_seconds: int
    rounds_played: int
    score_ct: int
    score_t: int
    winner_side: str
    players: List[ParsedPlayer] = field(default_factory=list)
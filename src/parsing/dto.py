from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ParsedPlayer:
    steam_id: str
    name: str
    team: Optional[str] = None
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    damage: float = 0.0
    headshots: int = 0
    first_kills: int = 0
    first_deaths: int = 0


@dataclass
class ParsedMatch:
    match_id: str
    map_name: str
    played_at: datetime
    score_ct: int = 0
    score_t: int = 0
    rounds_played: int = 0
    winner_side: str = "UNKNOWN"
    players: List[ParsedPlayer] = field(default_factory=list)
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ParsedRound:
    round_num: int
    winner_side: str  # "CT" или "T"
    win_reason: str   # Причина окончания (например, elimination, bomb_defused)
    end_tick: int = 0


@dataclass
class ParsedPlayer:
    steam_id: str
    name: str
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    damage: float = 0.0
    headshots: int = 0
    rounds_played: int = 1
    first_kills: int = 0
    first_deaths: int = 0
    team: Optional[str] = None


@dataclass
class ParsedMatch:
    match_id: str
    map_name: str
    duration_seconds: int = 0
    rounds_played: int = 0
    score_ct: int = 0
    score_t: int = 0
    winner_side: str = "UNKNOWN"
    played_at: datetime = field(default_factory=datetime.now)
    players: List[ParsedPlayer] = field(default_factory=list)
    rounds: List[ParsedRound] = field(default_factory=list)
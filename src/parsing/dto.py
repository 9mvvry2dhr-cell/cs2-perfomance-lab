from dataclasses import dataclass
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

    # Utility
    he_damage: float = 0.0
    inferno_damage: float = 0.0
    enemies_flashed: int = 0
    flash_duration: float = 0.0

    # Entry
    entry_kills: int = 0
    entry_deaths: int = 0

    # Clutch
    clutches_won: int = 0

    # Trade
    trade_kills: int = 0
    traded_deaths: int = 0

    # KAST
    kast_rounds: int = 0

    # Multikill
    two_k_rounds: int = 0
    three_k_rounds: int = 0
    four_k_rounds: int = 0
    five_k_rounds: int = 0

    # Survival
    survived_rounds: int = 0


@dataclass
class ParsedRound:
    round_num: int
    winner_side: str
    win_reason: str
    end_tick: int


@dataclass
class ParsedMatch:
    match_id: str
    map_name: str
    duration_seconds: int
    rounds_played: int
    score_ct: int
    score_t: int
    winner_side: str
    players: List[ParsedPlayer]
    rounds: List[ParsedRound]

    is_valid: bool = True
    validation_error: Optional[str] = None
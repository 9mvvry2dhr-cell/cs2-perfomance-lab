from dataclasses import dataclass
from typing import Dict, List, Mapping

from src.domain.insights import Finding, generate_player_findings
from src.domain.metrics import calculate_hs_percent, calculate_kd
from src.parsing.dto import ParsedMatch, ParsedPlayer


@dataclass(frozen=True)
class PlayerStats:
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


@dataclass(frozen=True)
class SideStats:
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


@dataclass(frozen=True)
class PlayerAnalysis:
    steam_id: str
    name: str
    stats: PlayerStats
    sides: Dict[str, SideStats]
    findings: List[Finding]


@dataclass(frozen=True)
class MatchAnalysis:
    match_id: str
    map_name: str
    duration_seconds: int
    rounds_played: int

    score_ct: int
    score_t: int
    winner_side: str

    is_valid: bool
    validation_error: str | None

    players: List[PlayerAnalysis]


def _percentage(
    numerator: float,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100,
        1,
    )


def _adr(
    damage: float,
    rounds: int,
) -> float:
    if rounds <= 0:
        return 0.0

    return round(
        damage / rounds,
        1,
    )


def _build_side_stats(
    bucket: Mapping[str, float],
) -> SideStats:
    rounds = int(
        bucket.get("rounds_played", 0)
    )

    damage = float(
        bucket.get("damage", 0.0)
    )

    kast_rounds = int(
        bucket.get("kast_rounds", 0)
    )

    survived_rounds = int(
        bucket.get("survived_rounds", 0)
    )

    return SideStats(
        rounds_played=rounds,
        kills=int(
            bucket.get("kills", 0)
        ),
        deaths=int(
            bucket.get("deaths", 0)
        ),
        damage=round(damage, 1),
        adr=_adr(
            damage,
            rounds,
        ),
        kast_rounds=kast_rounds,
        kast_pct=_percentage(
            kast_rounds,
            rounds,
        ),
        survived_rounds=survived_rounds,
        survival_pct=_percentage(
            survived_rounds,
            rounds,
        ),
        entry_kills=int(
            bucket.get("entry_kills", 0)
        ),
        entry_deaths=int(
            bucket.get("entry_deaths", 0)
        ),
    )


def build_player_analysis(
    player: ParsedPlayer,
    split_stats: Mapping[
        str,
        Mapping[str, float],
    ],
) -> PlayerAnalysis:
    rounds = int(
        player.rounds_played
    )

    stats = PlayerStats(
        rounds_played=rounds,
        kills=int(player.kills),
        deaths=int(player.deaths),
        assists=int(player.assists),
        headshots=int(
            player.headshots
        ),
        damage=round(
            float(player.damage),
            1,
        ),
        kd=calculate_kd(
            int(player.kills),
            int(player.deaths),
        ),
        adr=_adr(
            float(player.damage),
            rounds,
        ),
        headshot_pct=calculate_hs_percent(
            int(player.headshots),
            int(player.kills),
        ),
        kast_rounds=int(
            player.kast_rounds
        ),
        kast_pct=_percentage(
            player.kast_rounds,
            rounds,
        ),
        survived_rounds=int(
            player.survived_rounds
        ),
        survival_pct=_percentage(
            player.survived_rounds,
            rounds,
        ),
        entry_kills=int(
            player.entry_kills
        ),
        entry_deaths=int(
            player.entry_deaths
        ),
        he_damage=round(
            float(player.he_damage),
            1,
        ),
        inferno_damage=round(
            float(player.inferno_damage),
            1,
        ),
        enemies_flashed=int(
            player.enemies_flashed
        ),
        flash_duration=round(
            float(player.flash_duration),
            1,
        ),
        clutches_won=int(
            player.clutches_won
        ),
        trade_kills=int(
            player.trade_kills
        ),
        traded_deaths=int(
            player.traded_deaths
        ),
        two_k_rounds=int(
            player.two_k_rounds
        ),
        three_k_rounds=int(
            player.three_k_rounds
        ),
        four_k_rounds=int(
            player.four_k_rounds
        ),
        five_k_rounds=int(
            player.five_k_rounds
        ),
    )

    sides = {
        "CT": _build_side_stats(
            split_stats.get("CT", {})
        ),
        "T": _build_side_stats(
            split_stats.get("T", {})
        ),
    }

    return PlayerAnalysis(
        steam_id=str(player.steam_id),
        name=player.name,
        stats=stats,
        sides=sides,
        findings=generate_player_findings(
            split_stats
        ),
    )

def build_match_analysis(
    match: ParsedMatch,
    split_stats_by_player: Mapping[
        str,
        Mapping[
            str,
            Mapping[str, float],
        ],
    ],
) -> MatchAnalysis:
    """
    Build the stable analysis contract for one parsed match.
    """

    players = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        split_stats = (
            split_stats_by_player.get(
                steam_id,
                {},
            )
        )

        players.append(
            build_player_analysis(
                player,
                split_stats,
            )
        )

    return MatchAnalysis(
        match_id=match.match_id,
        map_name=match.map_name,
        duration_seconds=int(
            match.duration_seconds
        ),
        rounds_played=int(
            match.rounds_played
        ),
        score_ct=int(
            match.score_ct
        ),
        score_t=int(
            match.score_t
        ),
        winner_side=match.winner_side,
        is_valid=bool(
            match.is_valid
        ),
        validation_error=(
            match.validation_error
        ),
        players=players,
    )

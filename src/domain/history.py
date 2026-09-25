from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.analysis import PlayerStats, SideStats
from src.domain.insights import Finding
from src.domain.metrics import (
    calculate_adr,
    calculate_hs_percent,
    calculate_kd,
)


@dataclass(frozen=True)
class PlayerMatchHistoryItem:
    match_id: str
    analyzed_at: datetime

    map_name: str
    score_ct: int
    score_t: int

    player_name: str
    stats: PlayerStats
    findings: list[Finding]

    sides: dict[str, SideStats] = field(
        default_factory=dict
    )

    player_result: str = "unknown"


@dataclass(frozen=True)
class PlayerFindingFrequency:
    code: str
    category: str
    kind: str

    matches: int
    match_rate_pct: float


@dataclass(frozen=True)
class PlayerHistorySummary:
    steam_id: str
    player_name: str

    matches_analyzed: int
    stats: PlayerStats

    finding_frequency: list[
        PlayerFindingFrequency
    ]


def _percentage(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100,
        1,
    )


def build_player_history_summary(
    steam_id: str,
    matches: list[PlayerMatchHistoryItem],
) -> PlayerHistorySummary | None:
    """
    Build longitudinal player stats from persisted matches.

    Rates are always recalculated from accumulated raw totals.
    We intentionally do not average per-match ADR/KAST/KD.
    """
    if not matches:
        return None

    rounds_played = sum(
        item.stats.rounds_played
        for item in matches
    )

    kills = sum(
        item.stats.kills
        for item in matches
    )

    deaths = sum(
        item.stats.deaths
        for item in matches
    )

    assists = sum(
        item.stats.assists
        for item in matches
    )

    headshots = sum(
        item.stats.headshots
        for item in matches
    )

    damage = sum(
        item.stats.damage
        for item in matches
    )

    kast_rounds = sum(
        item.stats.kast_rounds
        for item in matches
    )

    survived_rounds = sum(
        item.stats.survived_rounds
        for item in matches
    )

    entry_kills = sum(
        item.stats.entry_kills
        for item in matches
    )

    entry_deaths = sum(
        item.stats.entry_deaths
        for item in matches
    )

    he_damage = sum(
        item.stats.he_damage
        for item in matches
    )

    inferno_damage = sum(
        item.stats.inferno_damage
        for item in matches
    )

    enemies_flashed = sum(
        item.stats.enemies_flashed
        for item in matches
    )

    flash_duration = sum(
        item.stats.flash_duration
        for item in matches
    )

    clutches_won = sum(
        item.stats.clutches_won
        for item in matches
    )

    trade_kills = sum(
        item.stats.trade_kills
        for item in matches
    )

    traded_deaths = sum(
        item.stats.traded_deaths
        for item in matches
    )

    two_k_rounds = sum(
        item.stats.two_k_rounds
        for item in matches
    )

    three_k_rounds = sum(
        item.stats.three_k_rounds
        for item in matches
    )

    four_k_rounds = sum(
        item.stats.four_k_rounds
        for item in matches
    )

    five_k_rounds = sum(
        item.stats.five_k_rounds
        for item in matches
    )

    stats = PlayerStats(
        rounds_played=rounds_played,
        kills=kills,
        deaths=deaths,
        assists=assists,
        headshots=headshots,
        damage=round(
            float(damage),
            1,
        ),
        kd=calculate_kd(
            kills,
            deaths,
        ),
        adr=calculate_adr(
            float(damage),
            rounds_played,
        ),
        headshot_pct=calculate_hs_percent(
            headshots,
            kills,
        ),
        kast_rounds=kast_rounds,
        kast_pct=_percentage(
            kast_rounds,
            rounds_played,
        ),
        survived_rounds=survived_rounds,
        survival_pct=_percentage(
            survived_rounds,
            rounds_played,
        ),
        entry_kills=entry_kills,
        entry_deaths=entry_deaths,
        he_damage=round(
            float(he_damage),
            1,
        ),
        inferno_damage=round(
            float(inferno_damage),
            1,
        ),
        enemies_flashed=enemies_flashed,
        flash_duration=round(
            float(flash_duration),
            1,
        ),
        clutches_won=clutches_won,
        trade_kills=trade_kills,
        traded_deaths=traded_deaths,
        two_k_rounds=two_k_rounds,
        three_k_rounds=three_k_rounds,
        four_k_rounds=four_k_rounds,
        five_k_rounds=five_k_rounds,
    )

    finding_counts: dict[str, int] = {}
    finding_meta: dict[
        str,
        tuple[str, str],
    ] = {}

    for item in matches:
        seen_codes: set[str] = set()

        for finding in item.findings:
            if finding.code in seen_codes:
                continue

            seen_codes.add(
                finding.code
            )

            finding_counts[finding.code] = (
                finding_counts.get(
                    finding.code,
                    0,
                )
                + 1
            )

            finding_meta.setdefault(
                finding.code,
                (
                    finding.category,
                    finding.kind,
                ),
            )

    frequency = []

    for code, count in finding_counts.items():
        category, kind = finding_meta[code]

        frequency.append(
            PlayerFindingFrequency(
                code=code,
                category=category,
                kind=kind,
                matches=count,
                match_rate_pct=round(
                    (
                        count
                        / len(matches)
                    )
                    * 100,
                    1,
                ),
            )
        )

    frequency.sort(
        key=lambda item: (
            -item.matches,
            item.code,
        )
    )

    return PlayerHistorySummary(
        steam_id=steam_id,
        player_name=matches[0].player_name,
        matches_analyzed=len(matches),
        stats=stats,
        finding_frequency=frequency,
    )

from dataclasses import dataclass
from typing import Dict, List, Literal, Mapping


FINDINGS_VERSION = "v2"


MIN_SIDE_ROUNDS = 6
MIN_ADR_GAP = 20.0
MIN_KAST_GAP_PCT = 15.0

MIN_ENTRY_SIDE_ROUNDS = 6

MIN_ENTRY_DEATHS = 3
MIN_ENTRY_DEATH_RATE_PCT = 25.0
MIN_ENTRY_DEATH_GAP = 2

MIN_ENTRY_KILLS = 3
MIN_ENTRY_KILL_RATE_PCT = 25.0
MIN_ENTRY_KILL_GAP = 2

MIN_SUPPORT_ROUNDS = 12

LOW_GRENADE_DAMAGE_PER_ROUND = 1.0
STRONG_GRENADE_DAMAGE_PER_ROUND = 8.0

LOW_ENEMIES_FLASHED_PER_ROUND = 0.10
LOW_FLASH_SECONDS_PER_ROUND = 0.15

STRONG_ENEMIES_FLASHED_PER_ROUND = 0.75
STRONG_FLASH_SECONDS_PER_ROUND = 1.80

STRONG_TRADE_MIN_KILLS = 4
STRONG_TRADE_KILLS_PER_ROUND = 0.23

STRONG_MULTIKILL_MIN_ROUNDS = 6
STRONG_MULTIKILL_ROUND_RATE = 0.33

MULTIPLE_CLUTCH_MIN_WINS = 2


@dataclass(frozen=True)
class Finding:
    code: str
    category: str
    kind: Literal["strength", "weakness"]
    severity: Literal["low", "medium", "high"]
    side: str
    evidence: Dict[str, float]


def _side_metrics(
    bucket: Mapping[str, float],
) -> tuple[int, float, float]:
    rounds = int(
        bucket.get("rounds_played", 0)
    )

    if rounds <= 0:
        return 0, 0.0, 0.0

    damage = float(
        bucket.get("damage", 0.0)
    )

    kast_rounds = int(
        bucket.get("kast_rounds", 0)
    )

    adr = round(
        damage / rounds,
        1,
    )

    kast_pct = round(
        (kast_rounds / rounds) * 100,
        1,
    )

    return (
        rounds,
        adr,
        kast_pct,
    )


def generate_side_findings(
    split_stats: Mapping[
        str,
        Mapping[str, float],
    ],
) -> List[Finding]:
    """
    Generate deterministic findings from verified CT/T stats.

    A side-performance gap is reported only when:
    - both sides have enough verified rounds;
    - ADR and KAST both point to the same weaker side;
    - both gaps exceed conservative thresholds.
    """

    ct_rounds, ct_adr, ct_kast = (
        _side_metrics(
            split_stats.get("CT", {})
        )
    )

    t_rounds, t_adr, t_kast = (
        _side_metrics(
            split_stats.get("T", {})
        )
    )

    if (
        ct_rounds < MIN_SIDE_ROUNDS
        or t_rounds < MIN_SIDE_ROUNDS
    ):
        return []

    adr_gap = round(
        abs(ct_adr - t_adr),
        1,
    )

    kast_gap = round(
        abs(ct_kast - t_kast),
        1,
    )

    if (
        adr_gap < MIN_ADR_GAP
        or kast_gap < MIN_KAST_GAP_PCT
    ):
        return []

    if (
        ct_adr > t_adr
        and ct_kast > t_kast
    ):
        weaker_side = "T"

    elif (
        t_adr > ct_adr
        and t_kast > ct_kast
    ):
        weaker_side = "CT"

    else:
        return []

    return [
        Finding(
            code="SIDE_PERFORMANCE_GAP",
            category="side_performance",
            kind="weakness",
            severity="medium",
            side=weaker_side,
            evidence={
                "ct_rounds": float(ct_rounds),
                "t_rounds": float(t_rounds),
                "ct_adr": ct_adr,
                "t_adr": t_adr,
                "ct_kast_pct": ct_kast,
                "t_kast_pct": t_kast,
                "adr_gap": adr_gap,
                "kast_gap_pct": kast_gap,
            },
        )
    ]

def generate_entry_findings(
    split_stats: Mapping[
        str,
        Mapping[str, float],
    ],
) -> List[Finding]:
    """
    Detect meaningful opening-duel patterns on a specific side.

    Weakness:
    - enough verified rounds;
    - at least three opening deaths;
    - at least two more opening deaths than kills;
    - opening-death rate is at least 25%.

    Strength:
    - enough verified rounds;
    - at least three opening kills;
    - at least two more opening kills than deaths;
    - opening-kill rate is at least 25%.
    """

    findings = []

    for side in ("CT", "T"):
        bucket = split_stats.get(
            side,
            {},
        )

        rounds = int(
            bucket.get(
                "rounds_played",
                0,
            )
        )

        entry_deaths = int(
            bucket.get(
                "entry_deaths",
                0,
            )
        )

        entry_kills = int(
            bucket.get(
                "entry_kills",
                0,
            )
        )

        if rounds < MIN_ENTRY_SIDE_ROUNDS:
            continue

        entry_death_gap = (
            entry_deaths
            - entry_kills
        )

        entry_kill_gap = (
            entry_kills
            - entry_deaths
        )

        entry_death_rate = round(
            (
                entry_deaths
                / rounds
            )
            * 100,
            1,
        )

        entry_kill_rate = round(
            (
                entry_kills
                / rounds
            )
            * 100,
            1,
        )

        if (
            entry_deaths >= MIN_ENTRY_DEATHS
            and entry_death_gap
            >= MIN_ENTRY_DEATH_GAP
            and entry_death_rate
            >= MIN_ENTRY_DEATH_RATE_PCT
        ):
            findings.append(
                Finding(
                    code="FREQUENT_OPENING_DEATHS",
                    category="entry",
                    kind="weakness",
                    severity="medium",
                    side=side,
                    evidence={
                        "rounds_played": float(rounds),
                        "entry_kills": float(entry_kills),
                        "entry_deaths": float(entry_deaths),
                        "entry_death_gap": float(
                            entry_death_gap
                        ),
                        "entry_death_rate_pct": (
                            entry_death_rate
                        ),
                    },
                )
            )

        if (
            entry_kills >= MIN_ENTRY_KILLS
            and entry_kill_gap
            >= MIN_ENTRY_KILL_GAP
            and entry_kill_rate
            >= MIN_ENTRY_KILL_RATE_PCT
        ):
            findings.append(
                Finding(
                    code="STRONG_OPENING_IMPACT",
                    category="entry",
                    kind="strength",
                    severity="medium",
                    side=side,
                    evidence={
                        "rounds_played": float(rounds),
                        "entry_kills": float(entry_kills),
                        "entry_deaths": float(entry_deaths),
                        "entry_kill_gap": float(
                            entry_kill_gap
                        ),
                        "entry_kill_rate_pct": (
                            entry_kill_rate
                        ),
                    },
                )
            )

    return findings


def generate_grenade_findings(
    overall_stats: Mapping[str, float],
) -> List[Finding]:
    """
    Detect unusually low or high verified HE + inferno damage.

    This rule intentionally describes damage impact only.
    It does not claim that overall grenade usage is good or bad,
    because smoke and flash value are different signals.
    """

    required = {
        "rounds_played",
        "he_damage",
        "inferno_damage",
    }

    if not required.issubset(
        overall_stats
    ):
        return []

    rounds = int(
        overall_stats["rounds_played"]
    )

    if rounds < MIN_SUPPORT_ROUNDS:
        return []

    he_damage = float(
        overall_stats["he_damage"]
    )

    inferno_damage = float(
        overall_stats["inferno_damage"]
    )

    grenade_damage = (
        he_damage
        + inferno_damage
    )

    damage_per_round = round(
        grenade_damage / rounds,
        2,
    )

    evidence = {
        "rounds_played": float(rounds),
        "he_damage": round(
            he_damage,
            1,
        ),
        "inferno_damage": round(
            inferno_damage,
            1,
        ),
        "grenade_damage": round(
            grenade_damage,
            1,
        ),
        "grenade_damage_per_round": (
            damage_per_round
        ),
    }

    if (
        damage_per_round
        <= LOW_GRENADE_DAMAGE_PER_ROUND
    ):
        return [
            Finding(
                code="LOW_GRENADE_DAMAGE_IMPACT",
                category="grenades",
                kind="weakness",
                severity="low",
                side="MATCH",
                evidence=evidence,
            )
        ]

    if (
        damage_per_round
        >= STRONG_GRENADE_DAMAGE_PER_ROUND
    ):
        return [
            Finding(
                code="STRONG_GRENADE_DAMAGE_IMPACT",
                category="grenades",
                kind="strength",
                severity="medium",
                side="MATCH",
                evidence=evidence,
            )
        ]

    return []


def generate_flash_findings(
    overall_stats: Mapping[str, float],
) -> List[Finding]:
    """
    Detect clearly low or clearly strong verified flash impact.

    Both enemy-count rate and blind-time rate must point in the
    same direction. Mixed signals deliberately produce no finding.
    """

    required = {
        "rounds_played",
        "enemies_flashed",
        "flash_duration",
    }

    if not required.issubset(
        overall_stats
    ):
        return []

    rounds = int(
        overall_stats["rounds_played"]
    )

    if rounds < MIN_SUPPORT_ROUNDS:
        return []

    enemies_flashed = int(
        overall_stats["enemies_flashed"]
    )

    flash_duration = float(
        overall_stats["flash_duration"]
    )

    flashed_per_round = round(
        enemies_flashed / rounds,
        2,
    )

    seconds_per_round = round(
        flash_duration / rounds,
        2,
    )

    evidence = {
        "rounds_played": float(rounds),
        "enemies_flashed": float(
            enemies_flashed
        ),
        "flash_duration": round(
            flash_duration,
            1,
        ),
        "enemies_flashed_per_round": (
            flashed_per_round
        ),
        "flash_seconds_per_round": (
            seconds_per_round
        ),
    }

    if (
        flashed_per_round
        <= LOW_ENEMIES_FLASHED_PER_ROUND
        and seconds_per_round
        <= LOW_FLASH_SECONDS_PER_ROUND
    ):
        return [
            Finding(
                code="LOW_FLASH_IMPACT",
                category="flash",
                kind="weakness",
                severity="low",
                side="MATCH",
                evidence=evidence,
            )
        ]

    if (
        flashed_per_round
        >= STRONG_ENEMIES_FLASHED_PER_ROUND
        and seconds_per_round
        >= STRONG_FLASH_SECONDS_PER_ROUND
    ):
        return [
            Finding(
                code="STRONG_FLASH_IMPACT",
                category="flash",
                kind="strength",
                severity="medium",
                side="MATCH",
                evidence=evidence,
            )
        ]

    return []


def generate_trade_findings(
    overall_stats: Mapping[str, float],
) -> List[Finding]:
    """
    Detect unusually strong verified trade impact.

    No low-trade weakness is emitted because the current contract
    does not expose the number of available trade opportunities.
    """

    required = {
        "rounds_played",
        "trade_kills",
    }

    if not required.issubset(
        overall_stats
    ):
        return []

    rounds = int(
        overall_stats["rounds_played"]
    )

    if rounds < MIN_SUPPORT_ROUNDS:
        return []

    trade_kills = int(
        overall_stats["trade_kills"]
    )

    trade_rate = round(
        trade_kills / rounds,
        3,
    )

    if (
        trade_kills
        < STRONG_TRADE_MIN_KILLS
        or trade_rate
        < STRONG_TRADE_KILLS_PER_ROUND
    ):
        return []

    return [
        Finding(
            code="STRONG_TRADE_IMPACT",
            category="trade",
            kind="strength",
            severity="medium",
            side="MATCH",
            evidence={
                "rounds_played": float(rounds),
                "trade_kills": float(
                    trade_kills
                ),
                "trade_kills_per_round": (
                    trade_rate
                ),
            },
        )
    ]


def generate_multikill_findings(
    overall_stats: Mapping[str, float],
) -> List[Finding]:
    """
    Detect unusually strong verified multikill impact.

    Only a strength is emitted. A low number of multikill rounds
    is not treated as a weakness because role and opportunity
    strongly affect this metric.
    """

    required = {
        "rounds_played",
        "two_k_rounds",
        "three_k_rounds",
        "four_k_rounds",
        "five_k_rounds",
    }

    if not required.issubset(
        overall_stats
    ):
        return []

    rounds = int(
        overall_stats["rounds_played"]
    )

    if rounds < MIN_SUPPORT_ROUNDS:
        return []

    two_k = int(
        overall_stats["two_k_rounds"]
    )

    three_k = int(
        overall_stats["three_k_rounds"]
    )

    four_k = int(
        overall_stats["four_k_rounds"]
    )

    five_k = int(
        overall_stats["five_k_rounds"]
    )

    multikill_rounds = (
        two_k
        + three_k
        + four_k
        + five_k
    )

    multikill_rate = round(
        multikill_rounds / rounds,
        3,
    )

    if (
        multikill_rounds
        < STRONG_MULTIKILL_MIN_ROUNDS
        or multikill_rate
        < STRONG_MULTIKILL_ROUND_RATE
    ):
        return []

    return [
        Finding(
            code="STRONG_MULTIKILL_IMPACT",
            category="multikill",
            kind="strength",
            severity="medium",
            side="MATCH",
            evidence={
                "rounds_played": float(rounds),
                "multikill_rounds": float(
                    multikill_rounds
                ),
                "multikill_round_rate": (
                    multikill_rate
                ),
                "two_k_rounds": float(two_k),
                "three_k_rounds": float(
                    three_k
                ),
                "four_k_rounds": float(
                    four_k
                ),
                "five_k_rounds": float(
                    five_k
                ),
            },
        )
    ]


def generate_clutch_findings(
    overall_stats: Mapping[str, float],
) -> List[Finding]:
    """
    Detect multiple verified clutch wins in one match.

    No clutch weakness is emitted because the current contract
    does not expose clutch opportunities or attempts.
    """

    required = {
        "rounds_played",
        "clutches_won",
    }

    if not required.issubset(
        overall_stats
    ):
        return []

    rounds = int(
        overall_stats["rounds_played"]
    )

    if rounds < MIN_SUPPORT_ROUNDS:
        return []

    clutches_won = int(
        overall_stats["clutches_won"]
    )

    if (
        clutches_won
        < MULTIPLE_CLUTCH_MIN_WINS
    ):
        return []

    return [
        Finding(
            code="MULTIPLE_CLUTCH_WINS",
            category="clutch",
            kind="strength",
            severity="medium",
            side="MATCH",
            evidence={
                "rounds_played": float(rounds),
                "clutches_won": float(
                    clutches_won
                ),
            },
        )
    ]


def generate_player_findings(
    split_stats: Mapping[
        str,
        Mapping[str, float],
    ],
    overall_stats: Mapping[
        str,
        float,
    ] | None = None,
) -> List[Finding]:
    """
    Generate all verified findings for one player.
    """

    findings: List[Finding] = []

    findings.extend(
        generate_side_findings(
            split_stats
        )
    )

    findings.extend(
        generate_entry_findings(
            split_stats
        )
    )

    if overall_stats is not None:
        findings.extend(
            generate_grenade_findings(
                overall_stats
            )
        )

        findings.extend(
            generate_flash_findings(
                overall_stats
            )
        )

        findings.extend(
            generate_trade_findings(
                overall_stats
            )
        )

        findings.extend(
            generate_multikill_findings(
                overall_stats
            )
        )

        findings.extend(
            generate_clutch_findings(
                overall_stats
            )
        )

    return findings

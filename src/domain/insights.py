from dataclasses import dataclass
from typing import Dict, List, Mapping


MIN_SIDE_ROUNDS = 6
MIN_ADR_GAP = 20.0
MIN_KAST_GAP_PCT = 15.0

MIN_ENTRY_SIDE_ROUNDS = 6
MIN_ENTRY_DEATHS = 3
MIN_ENTRY_DEATH_RATE_PCT = 25.0
MIN_ENTRY_DEATH_GAP = 2


@dataclass(frozen=True)
class Finding:
    code: str
    category: str
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
    Detect frequent opening deaths on a specific side.

    A finding is emitted only when:
    - enough verified rounds were played on that side;
    - the player has at least three opening deaths;
    - opening-death rate is at least 25%.
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

        if entry_deaths < MIN_ENTRY_DEATHS:
            continue

        entry_death_gap = (
            entry_deaths
            - entry_kills
        )

        if entry_death_gap < MIN_ENTRY_DEATH_GAP:
            continue

        rate = round(
            (
                entry_deaths
                / rounds
            )
            * 100,
            1,
        )

        if rate < MIN_ENTRY_DEATH_RATE_PCT:
            continue

        findings.append(
            Finding(
                code="FREQUENT_OPENING_DEATHS",
                category="entry",
                side=side,
                evidence={
                    "rounds_played": float(rounds),
                    "entry_kills": float(entry_kills),
                    "entry_deaths": float(entry_deaths),
                    "entry_death_gap": float(entry_death_gap),
                    "entry_death_rate_pct": rate,
                },
            )
        )

    return findings

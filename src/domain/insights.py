from dataclasses import dataclass
from typing import Dict, List, Mapping


MIN_SIDE_ROUNDS = 6
MIN_ADR_GAP = 20.0
MIN_KAST_GAP_PCT = 15.0


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

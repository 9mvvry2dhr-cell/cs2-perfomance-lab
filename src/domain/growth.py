from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


GrowthKind = Literal[
    "growth",
    "strength",
    "neutral",
    "insufficient",
]

Confidence = Literal[
    "none",
    "low",
    "medium",
    "high",
]


MIN_CONTESTED_DUELS = 4
WEAK_DUEL_WIN_RATE_MAX = 35.0
STRONG_DUEL_WIN_RATE_MIN = 70.0


@dataclass(frozen=True)
class GrowthSignal:
    code: str
    kind: GrowthKind
    confidence: Confidence
    evidence: dict[
        str,
        Any,
    ]


def _int_value(
    metrics: Mapping[
        str,
        int | float | None,
    ],
    key: str,
) -> int:
    value = metrics.get(key)

    if value is None:
        return 0

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _float_value(
    metrics: Mapping[
        str,
        int | float | None,
    ],
    key: str,
) -> float | None:
    value = metrics.get(key)

    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def evaluate_duel_growth(
    metrics: Mapping[
        str,
        int | float | None,
    ],
) -> GrowthSignal:
    """
    Evaluate duel realization independently of match result.

    Important:
    - this does not judge aim;
    - this does not use win/loss of the match;
    - this does not infer weakness from K/D;
    - insufficient sample stays insufficient.
    """

    contested = _int_value(
        metrics,
        "contested_duels",
    )

    contested_wins = _int_value(
        metrics,
        "contested_wins",
    )

    contested_losses = _int_value(
        metrics,
        "contested_losses",
    )

    win_rate = _float_value(
        metrics,
        "contested_win_rate",
    )

    if (
        win_rate is None
        and contested > 0
    ):
        win_rate = round(
            contested_wins
            / contested
            * 100,
            1,
        )

    lost_after_first = _int_value(
        metrics,
        "lost_after_first_damage",
    )

    close_losses = _int_value(
        metrics,
        "close_losses",
    )

    no_return_losses = _int_value(
        metrics,
        "no_return_losses",
    )

    non_instant_no_return = _int_value(
        metrics,
        "non_instant_no_return_losses",
    )

    instant_losses = _int_value(
        metrics,
        "instant_losses",
    )

    evidence = {
        "contested_duels": contested,
        "contested_wins": contested_wins,
        "contested_losses": (
            contested_losses
        ),
        "contested_win_rate": win_rate,
        "lost_after_first_damage": (
            lost_after_first
        ),
        "close_losses": close_losses,
        "no_return_losses": (
            no_return_losses
        ),
        "non_instant_no_return_losses": (
            non_instant_no_return
        ),
        "instant_losses": instant_losses,
    }

    if (
        contested
        < MIN_CONTESTED_DUELS
        or win_rate is None
    ):
        return GrowthSignal(
            code="DUEL_REALIZATION",
            kind="insufficient",
            confidence="none",
            evidence=evidence,
        )

    if (
        win_rate
        <= WEAK_DUEL_WIN_RATE_MAX
    ):
        supporting_losses = (
            lost_after_first
            + close_losses
        )

        confidence: Confidence = (
            "high"
            if (
                contested >= 7
                and supporting_losses >= 2
            )
            else "medium"
        )

        return GrowthSignal(
            code="DUEL_REALIZATION",
            kind="growth",
            confidence=confidence,
            evidence=evidence,
        )

    if (
        win_rate
        >= STRONG_DUEL_WIN_RATE_MIN
    ):
        confidence = (
            "high"
            if contested >= 8
            else "medium"
        )

        return GrowthSignal(
            code="DUEL_REALIZATION",
            kind="strength",
            confidence=confidence,
            evidence=evidence,
        )

    return GrowthSignal(
        code="DUEL_REALIZATION",
        kind="neutral",
        confidence="medium",
        evidence=evidence,
    )
from __future__ import annotations

from typing import Literal

from src.metrics.round_state import (
    RoundAdvantageSummary,
)


RoundSwingType = Literal[
    "no_advantage",
    "clean_conversion",
    "regained",
    "comeback",
    "stolen",
    "swing",
]


def classify_round_swing(
    summary: RoundAdvantageSummary,
) -> RoundSwingType:
    """
    Classify the numerical-advantage story of one round.

    clean_conversion
        First advantage was converted without losing it.

    regained
        First advantage disappeared to equal numbers,
        was regained, and the team still won.
        The opponent never gained a numerical lead.

    comeback
        The first-advantage team later fell numerically
        behind but still won the round.

    stolen
        The first-advantage team failed to convert and
        did not regain control after a real reversal.

    swing
        The advantage genuinely changed sides and the
        first-advantage team later regained a lead,
        but still lost the round.
    """

    if (
        summary.first_advantage_team is None
        or summary.converted_first_advantage
        is None
    ):
        return "no_advantage"

    if summary.converted_first_advantage:
        if summary.advantage_reversed:
            return "comeback"

        if (
            summary.advantage_lost
            and summary.advantage_restored
        ):
            return "regained"

        return "clean_conversion"

    if (
        summary.advantage_reversed
        and summary.advantage_restored
    ):
        return "swing"

    return "stolen"

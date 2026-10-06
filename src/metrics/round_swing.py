from __future__ import annotations

from typing import Literal

from src.metrics.round_state import (
    RoundAdvantageSummary,
)


RoundSwingType = Literal[
    "no_advantage",
    "clean_conversion",
    "stolen",
    "recovered",
    "swing",
]


def classify_round_swing(
    summary: RoundAdvantageSummary,
) -> RoundSwingType:
    """
    Classify the numerical-advantage story of one round.

    no_advantage
        No meaningful first numerical advantage was detected.

    clean_conversion
        The team that gained the first advantage kept control
        and converted the round.

    stolen
        The team that gained the first advantage lost it and
        ultimately lost the round without restoring it.

    recovered
        The first-advantage team lost control, restored it,
        and still converted the round.

    swing
        The first-advantage team lost control, restored it,
        but ultimately lost the round anyway.
    """

    if (
        summary.first_advantage_team is None
        or summary.converted_first_advantage
        is None
    ):
        return "no_advantage"

    if summary.converted_first_advantage:
        if (
            summary.advantage_lost
            and summary.advantage_restored
        ):
            return "recovered"

        return "clean_conversion"

    if summary.advantage_restored:
        return "swing"

    return "stolen"

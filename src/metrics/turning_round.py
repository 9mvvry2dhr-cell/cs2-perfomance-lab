from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.metrics.match_flow import (
    RoundScoreState,
    TeamIdentity,
)
from src.metrics.round_state import (
    RoundAdvantageSummary,
)
from src.metrics.round_swing import (
    RoundSwingType,
    classify_round_swing,
)


STRONG_SWING_TYPES = {
    "stolen",
    "comeback",
    "swing",
}


@dataclass(frozen=True)
class TurningRound:
    """
    One confirmed match-level momentum pivot.

    This is intentionally not an opaque impact score.
    Every selected round carries explicit factual reasons.
    """

    round_num: int
    winner_team: TeamIdentity
    swing_type: RoundSwingType

    score_a_before: int
    score_b_before: int
    score_a_after: int
    score_b_after: int

    opponent_streak_before: int
    winner_run_length: int

    reasons: tuple[str, ...]


def _score_for_team(
    state: RoundScoreState,
    team: TeamIdentity,
    *,
    after: bool,
) -> int:
    if team == "team_a":
        return (
            state.score_a_after
            if after
            else state.score_a_before
        )

    return (
        state.score_b_after
        if after
        else state.score_b_before
    )


def _other_team(
    team: TeamIdentity,
) -> TeamIdentity:
    return (
        "team_b"
        if team == "team_a"
        else "team_a"
    )


def _opponent_streak_before(
    timeline: Sequence[RoundScoreState],
    index: int,
) -> int:
    winner = timeline[index].winner_team
    count = 0

    for position in range(
        index - 1,
        -1,
        -1,
    ):
        if (
            timeline[position].winner_team
            == winner
        ):
            break

        count += 1

    return count


def _winner_run_length(
    timeline: Sequence[RoundScoreState],
    index: int,
) -> int:
    winner = timeline[index].winner_team
    count = 0

    for position in range(
        index,
        len(timeline),
    ):
        if (
            timeline[position].winner_team
            != winner
        ):
            break

        count += 1

    return count


def detect_turning_rounds(
    timeline: Sequence[RoundScoreState],
    advantage_by_round: Mapping[
        int,
        RoundAdvantageSummary,
    ],
) -> list[TurningRound]:
    """
    Detect confirmed momentum changes.

    A turning round must:
    - start a new winning run;
    - lead to at least three consecutive round wins;
    - carry at least one meaningful match/round signal.
    """

    results: list[TurningRound] = []

    for index, state in enumerate(
        timeline
    ):
        # The opening run of the match cannot be a turning
        # point because there is no previous match direction
        # to reverse.
        if index == 0:
            continue

        # Only the first round of a new run can be
        # considered the cause of that run.
        if (
            index > 0
            and timeline[index - 1].winner_team
            == state.winner_team
        ):
            continue

        run_length = _winner_run_length(
            timeline,
            index,
        )

        if run_length < 3:
            continue

        summary = advantage_by_round.get(
            state.round_num
        )

        swing_type: RoundSwingType = (
            classify_round_swing(summary)
            if summary is not None
            else "no_advantage"
        )

        opponent = _other_team(
            state.winner_team
        )

        winner_before = _score_for_team(
            state,
            state.winner_team,
            after=False,
        )

        opponent_before = _score_for_team(
            state,
            opponent,
            after=False,
        )

        winner_after = _score_for_team(
            state,
            state.winner_team,
            after=True,
        )

        opponent_after = _score_for_team(
            state,
            opponent,
            after=True,
        )

        opponent_streak = (
            _opponent_streak_before(
                timeline,
                index,
            )
        )

        reasons: list[str] = []

        if opponent_streak >= 2:
            reasons.append(
                "broke_opponent_streak"
            )

        if winner_after == opponent_after:
            reasons.append(
                "equalized_score"
            )

        if (
            winner_before
            <= opponent_before
            and winner_after
            > opponent_after
        ):
            reasons.append(
                "took_lead"
            )

        if swing_type in STRONG_SWING_TYPES:
            reasons.append(
                "strong_round_swing"
            )

        if not reasons:
            continue

        results.append(
            TurningRound(
                round_num=state.round_num,
                winner_team=state.winner_team,
                swing_type=swing_type,
                score_a_before=(
                    state.score_a_before
                ),
                score_b_before=(
                    state.score_b_before
                ),
                score_a_after=(
                    state.score_a_after
                ),
                score_b_after=(
                    state.score_b_after
                ),
                opponent_streak_before=(
                    opponent_streak
                ),
                winner_run_length=(
                    run_length
                ),
                reasons=tuple(reasons),
            )
        )

    return results

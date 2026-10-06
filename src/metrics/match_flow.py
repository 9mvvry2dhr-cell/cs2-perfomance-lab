from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from src.metrics.splits import PlayerRoundSide
from src.parsing.dto import ParsedRound


TeamIdentity = Literal[
    "team_a",
    "team_b",
]


@dataclass(frozen=True)
class RoundScoreState:
    """
    Stable match score around one confirmed round.

    team_a / team_b are permanent team identities based on
    player rosters, not T/CT sides.
    """

    round_num: int
    winner_team: TeamIdentity
    winner_side: str

    score_a_before: int
    score_b_before: int

    score_a_after: int
    score_b_after: int


def _build_side_rosters(
    side_events: Iterable[PlayerRoundSide],
) -> dict[int, dict[str, set[str]]]:
    rosters: dict[
        int,
        dict[str, set[str]],
    ] = {}

    for event in side_events:
        if event.side not in {
            "T",
            "CT",
        }:
            continue

        round_roster = rosters.setdefault(
            event.round_num,
            {
                "T": set(),
                "CT": set(),
            },
        )

        round_roster[
            event.side
        ].add(
            str(event.steam_id)
        )

    return rosters


def build_round_score_timeline(
    rounds: Sequence[ParsedRound],
    side_events: Iterable[PlayerRoundSide],
) -> list[RoundScoreState]:
    """
    Build chronological score using stable player-team identity.

    team_a:
        players who occupied T in the first usable roster.

    team_b:
        players who occupied CT in the first usable roster.

    Later side swaps do not matter. The winner of each round
    is resolved by roster overlap with those original teams.

    Fail closed:
        if a round winner cannot be mapped unambiguously,
        no score timeline is returned.
    """

    if not rounds:
        return []

    ordered_rounds = sorted(
        rounds,
        key=lambda item: item.round_num,
    )

    rosters = _build_side_rosters(
        side_events
    )

    team_a: set[str] | None = None
    team_b: set[str] | None = None

    for round_data in ordered_rounds:
        roster = rosters.get(
            round_data.round_num
        )

        if not roster:
            continue

        t_players = set(
            roster.get(
                "T",
                set(),
            )
        )

        ct_players = set(
            roster.get(
                "CT",
                set(),
            )
        )

        if (
            not t_players
            or not ct_players
            or t_players & ct_players
        ):
            continue

        team_a = t_players
        team_b = ct_players
        break

    if (
        not team_a
        or not team_b
    ):
        return []

    score_a = 0
    score_b = 0

    timeline: list[
        RoundScoreState
    ] = []

    for round_data in ordered_rounds:
        if round_data.winner_side not in {
            "T",
            "CT",
        }:
            return []

        roster = rosters.get(
            round_data.round_num
        )

        if not roster:
            return []

        winner_players = set(
            roster.get(
                round_data.winner_side,
                set(),
            )
        )

        if not winner_players:
            return []

        team_a_votes = len(
            winner_players
            & team_a
        )

        team_b_votes = len(
            winner_players
            & team_b
        )

        if team_a_votes == team_b_votes:
            return []

        winner_team: TeamIdentity = (
            "team_a"
            if team_a_votes
            > team_b_votes
            else "team_b"
        )

        score_a_before = score_a
        score_b_before = score_b

        if winner_team == "team_a":
            score_a += 1
        else:
            score_b += 1

        timeline.append(
            RoundScoreState(
                round_num=(
                    round_data.round_num
                ),
                winner_team=winner_team,
                winner_side=(
                    round_data.winner_side
                ),
                score_a_before=(
                    score_a_before
                ),
                score_b_before=(
                    score_b_before
                ),
                score_a_after=score_a,
                score_b_after=score_b,
            )
        )

    return timeline

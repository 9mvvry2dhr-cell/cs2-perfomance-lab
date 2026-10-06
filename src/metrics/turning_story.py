from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from src.metrics.match_flow import (
    RoundScoreState,
)
from src.metrics.round_state import (
    RoundStateTransition,
    TEAM_CT,
    TEAM_T,
)
from src.metrics.turning_round import (
    TurningRound,
)


ControlEventType = Literal[
    "control_gain",
    "control_loss",
    "reversal",
    "equalizer",
]

RoundResolutionType = Literal[
    "sustained_control",
    "final_elimination",
    "unresolved",
]


@dataclass(frozen=True)
class TurningControlEvent:
    """
    One verified change in numerical control from the
    eventual round winner's point of view.
    """

    round_num: int
    tick: int

    event_type: ControlEventType
    decisive: bool

    attacker: str | None
    victim: str

    attacker_team: int | None
    victim_team: int
    cause: str

    state_before: str
    state_after: str

    winner_advantage_before: int
    winner_advantage_after: int


@dataclass(frozen=True)
class TurningRoundStory:
    """
    Verified control story of one turning round.
    """

    round_num: int
    winner_team_num: int

    events: tuple[
        TurningControlEvent,
        ...
    ]

    decisive_tick: int | None
    resolution: RoundResolutionType


def _winner_team_num(
    state: RoundScoreState,
) -> int | None:
    if state.winner_side == "T":
        return TEAM_T

    if state.winner_side == "CT":
        return TEAM_CT

    return None


def _advantage(
    *,
    t_alive: int,
    ct_alive: int,
    winner_team_num: int,
) -> int:
    if winner_team_num == TEAM_T:
        return t_alive - ct_alive

    return ct_alive - t_alive


def build_turning_round_stories(
    turning_rounds: Sequence[
        TurningRound
    ],
    timeline: Sequence[
        RoundScoreState
    ],
    transitions: Sequence[
        RoundStateTransition
    ],
) -> list[TurningRoundStory]:
    """
    Describe how numerical control changed inside each
    confirmed turning round.

    Decisive control:
        earliest transition after which the eventual winner
        remains strictly numerically ahead for the rest of
        the recorded death sequence.

    Returning only to equal numbers is not decisive control.
    """

    timeline_by_round = {
        item.round_num: item
        for item in timeline
    }

    transitions_by_round: dict[
        int,
        list[RoundStateTransition],
    ] = {}

    for transition in transitions:
        transitions_by_round.setdefault(
            transition.round_num,
            [],
        ).append(
            transition
        )

    stories: list[
        TurningRoundStory
    ] = []

    for turning_round in turning_rounds:
        state = timeline_by_round.get(
            turning_round.round_num
        )

        if state is None:
            continue

        winner_team_num = (
            _winner_team_num(
                state
            )
        )

        if winner_team_num is None:
            continue

        round_transitions = sorted(
            transitions_by_round.get(
                turning_round.round_num,
                [],
            ),
            key=lambda item: item.tick,
        )

        advantages_after = [
            _advantage(
                t_alive=(
                    transition.t_alive_after
                ),
                ct_alive=(
                    transition.ct_alive_after
                ),
                winner_team_num=(
                    winner_team_num
                ),
            )
            for transition
            in round_transitions
        ]

        decisive_index = None

        for index, after in enumerate(
            advantages_after
        ):
            if after <= 0:
                continue

            transition = (
                round_transitions[index]
            )

            # A terminal elimination such as 1v1 -> 0v1
            # is a round-closing kill, not a meaningful
            # acquisition of sustained numerical control.
            if (
                transition.t_alive_after == 0
                or transition.ct_alive_after == 0
            ):
                continue

            if all(
                later > 0
                for later
                in advantages_after[index:]
            ):
                decisive_index = index
                break

        control_events: list[
            TurningControlEvent
        ] = []

        for index, transition in enumerate(
            round_transitions
        ):
            before = _advantage(
                t_alive=(
                    transition.t_alive_before
                ),
                ct_alive=(
                    transition.ct_alive_before
                ),
                winner_team_num=(
                    winner_team_num
                ),
            )

            after = _advantage(
                t_alive=(
                    transition.t_alive_after
                ),
                ct_alive=(
                    transition.ct_alive_after
                ),
                winner_team_num=(
                    winner_team_num
                ),
            )

            event_type: (
                ControlEventType
                | None
            ) = None

            if before <= 0 and after > 0:
                event_type = "control_gain"

            elif before > 0 and after <= 0:
                event_type = "control_loss"

            elif before >= 0 and after < 0:
                event_type = "reversal"

            elif before < 0 and after == 0:
                event_type = "equalizer"

            if event_type is None:
                continue

            control_events.append(
                TurningControlEvent(
                    round_num=(
                        transition.round_num
                    ),
                    tick=transition.tick,
                    event_type=event_type,
                    decisive=(
                        index
                        == decisive_index
                    ),
                    attacker=(
                        transition.attacker
                    ),
                    victim=(
                        transition.victim
                    ),
                    attacker_team=(
                        transition.attacker_team
                    ),
                    victim_team=(
                        transition.victim_team
                    ),
                    cause=transition.cause,
                    state_before=(
                        transition.state_before
                    ),
                    state_after=(
                        transition.state_after
                    ),
                    winner_advantage_before=(
                        before
                    ),
                    winner_advantage_after=(
                        after
                    ),
                )
            )

        decisive_tick = (
            round_transitions[
                decisive_index
            ].tick
            if decisive_index
            is not None
            else None
        )

        resolution = (
            "sustained_control"
            if decisive_tick is not None
            else "unresolved"
        )

        if (
            decisive_tick is None
            and round_transitions
        ):
            last = round_transitions[-1]

            winner_alive = (
                last.t_alive_after
                if winner_team_num == TEAM_T
                else last.ct_alive_after
            )

            loser_alive = (
                last.ct_alive_after
                if winner_team_num == TEAM_T
                else last.t_alive_after
            )

            if (
                winner_alive > 0
                and loser_alive == 0
            ):
                resolution = (
                    "final_elimination"
                )

        stories.append(
            TurningRoundStory(
                round_num=(
                    turning_round.round_num
                ),
                winner_team_num=(
                    winner_team_num
                ),
                events=tuple(
                    control_events
                ),
                decisive_tick=decisive_tick,
                resolution=resolution,
            )
        )

    return stories

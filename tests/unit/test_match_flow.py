from src.metrics.match_flow import (
    build_round_score_timeline,
)
from src.metrics.splits import (
    PlayerRoundSide,
)
from src.parsing.dto import (
    ParsedRound,
)


TEAM_A = [
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
]

TEAM_B = [
    "b1",
    "b2",
    "b3",
    "b4",
    "b5",
]


def make_round(
    round_num,
    winner_side,
):
    return ParsedRound(
        round_num=round_num,
        winner_side=winner_side,
        win_reason="test",
        end_tick=round_num * 100,
    )


def add_roster(
    events,
    round_num,
    *,
    a_side,
    b_side,
    missing_a=None,
):
    missing_a = (
        missing_a
        or set()
    )

    for player in TEAM_A:
        if player in missing_a:
            continue

        events.append(
            PlayerRoundSide(
                round_num=round_num,
                steam_id=player,
                side=a_side,
            )
        )

    for player in TEAM_B:
        events.append(
            PlayerRoundSide(
                round_num=round_num,
                steam_id=player,
                side=b_side,
            )
        )


def test_score_survives_side_swap():
    rounds = [
        make_round(1, "T"),
        make_round(2, "CT"),
        make_round(3, "CT"),
    ]

    events = []

    add_roster(
        events,
        1,
        a_side="T",
        b_side="CT",
    )

    add_roster(
        events,
        2,
        a_side="T",
        b_side="CT",
    )

    # Teams swap sides.
    add_roster(
        events,
        3,
        a_side="CT",
        b_side="T",
    )

    timeline = (
        build_round_score_timeline(
            rounds,
            events,
        )
    )

    assert [
        item.winner_team
        for item in timeline
    ] == [
        "team_a",
        "team_b",
        "team_a",
    ]

    assert (
        timeline[-1].score_a_after,
        timeline[-1].score_b_after,
    ) == (
        2,
        1,
    )


def test_no_fixed_halftime_assumption():
    rounds = [
        make_round(1, "T"),
        make_round(2, "T"),
        make_round(3, "CT"),
        make_round(4, "CT"),
    ]

    events = []

    add_roster(
        events,
        1,
        a_side="T",
        b_side="CT",
    )

    add_roster(
        events,
        2,
        a_side="CT",
        b_side="T",
    )

    add_roster(
        events,
        3,
        a_side="T",
        b_side="CT",
    )

    add_roster(
        events,
        4,
        a_side="CT",
        b_side="T",
    )

    timeline = (
        build_round_score_timeline(
            rounds,
            events,
        )
    )

    assert [
        item.winner_team
        for item in timeline
    ] == [
        "team_a",
        "team_b",
        "team_b",
        "team_a",
    ]

    assert (
        timeline[-1].score_a_after,
        timeline[-1].score_b_after,
    ) == (
        2,
        2,
    )


def test_disconnect_does_not_break_identity():
    rounds = [
        make_round(1, "T"),
        make_round(2, "CT"),
    ]

    events = []

    add_roster(
        events,
        1,
        a_side="T",
        b_side="CT",
    )

    add_roster(
        events,
        2,
        a_side="CT",
        b_side="T",
        missing_a={"a5"},
    )

    timeline = (
        build_round_score_timeline(
            rounds,
            events,
        )
    )

    assert len(timeline) == 2

    assert (
        timeline[1].winner_team
        == "team_a"
    )


def test_ambiguous_winner_fails_closed():
    rounds = [
        make_round(1, "T"),
        make_round(2, "T"),
    ]

    events = []

    add_roster(
        events,
        1,
        a_side="T",
        b_side="CT",
    )

    # No usable roster for round 2.
    timeline = (
        build_round_score_timeline(
            rounds,
            events,
        )
    )

    assert timeline == []

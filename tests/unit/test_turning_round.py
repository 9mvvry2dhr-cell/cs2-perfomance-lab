from src.metrics.match_flow import (
    RoundScoreState,
)
from src.metrics.round_state import (
    RoundAdvantageSummary,
    TEAM_CT,
)
from src.metrics.turning_round import (
    detect_turning_rounds,
)


def state(
    n,
    winner,
    before,
    after,
):
    return RoundScoreState(
        round_num=n,
        winner_team=winner,
        winner_side="CT",
        score_a_before=before[0],
        score_b_before=before[1],
        score_a_after=after[0],
        score_b_after=after[1],
    )


def summary(
    n,
    *,
    converted=True,
    lost=False,
    restored=False,
    reversed_advantage=False,
):
    # max advantages encode reversal.
    return RoundAdvantageSummary(
        round_num=n,
        winner_team=TEAM_CT,
        first_advantage_team=TEAM_CT,
        first_advantage_tick=100,
        first_advantage_by="1",
        converted_first_advantage=converted,
        advantage_lost=lost,
        advantage_restored=restored,
        comeback_team=(
            TEAM_CT
            if reversed_advantage
            else None
        ),
        max_t_advantage=(
            1
            if reversed_advantage
            else 0
        ),
        max_ct_advantage=2,
    )


def test_streak_break_starts_confirmed_turn():
    timeline = [
        state(1, "team_b", (0, 0), (0, 1)),
        state(2, "team_b", (0, 1), (0, 2)),
        state(3, "team_b", (0, 2), (0, 3)),
        state(4, "team_a", (0, 3), (1, 3)),
        state(5, "team_a", (1, 3), (2, 3)),
        state(6, "team_a", (2, 3), (3, 3)),
    ]

    turns = detect_turning_rounds(
        timeline,
        {},
    )

    assert len(turns) == 1
    assert turns[0].round_num == 4
    assert (
        "broke_opponent_streak"
        in turns[0].reasons
    )
    assert turns[0].winner_run_length == 3


def test_equalizer_can_start_turn():
    timeline = [
        state(1, "team_a", (0, 0), (1, 0)),
        state(2, "team_b", (1, 0), (1, 1)),
        state(3, "team_b", (1, 1), (1, 2)),
        state(4, "team_a", (1, 2), (2, 2)),
        state(5, "team_a", (2, 2), (3, 2)),
        state(6, "team_a", (3, 2), (4, 2)),
    ]

    turns = detect_turning_rounds(
        timeline,
        {},
    )

    assert len(turns) == 1
    assert turns[0].round_num == 4
    assert (
        "equalized_score"
        in turns[0].reasons
    )


def test_false_turn_is_rejected():
    timeline = [
        state(1, "team_a", (0, 0), (1, 0)),
        state(2, "team_a", (1, 0), (2, 0)),
        state(3, "team_b", (2, 0), (2, 1)),
        state(4, "team_a", (2, 1), (3, 1)),
        state(5, "team_a", (3, 1), (4, 1)),
        state(6, "team_a", (4, 1), (5, 1)),
    ]

    turns = detect_turning_rounds(
        timeline,
        {},
    )

    assert all(
        item.round_num != 3
        for item in turns
    )


def test_strong_swing_still_needs_confirmation():
    timeline = [
        state(1, "team_a", (0, 0), (1, 0)),
        state(2, "team_b", (1, 0), (1, 1)),
        state(3, "team_a", (1, 1), (2, 1)),
    ]

    summaries = {
        2: summary(
            2,
            converted=True,
            lost=True,
            restored=True,
            reversed_advantage=True,
        )
    }

    turns = detect_turning_rounds(
        timeline,
        summaries,
    )

    assert turns == []

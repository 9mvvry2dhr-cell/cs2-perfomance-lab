from src.metrics.round_state import (
    RoundAdvantageSummary,
    TEAM_CT,
    TEAM_T,
)
from src.metrics.round_swing import (
    classify_round_swing,
)


def make_summary(
    *,
    winner_team=TEAM_CT,
    first_advantage_team=TEAM_CT,
    converted=True,
    lost=False,
    restored=False,
    comeback_team=None,
    max_t_advantage=0,
    max_ct_advantage=1,
):
    return RoundAdvantageSummary(
        round_num=1,
        winner_team=winner_team,
        first_advantage_team=(
            first_advantage_team
        ),
        first_advantage_tick=100,
        first_advantage_by="111",
        converted_first_advantage=(
            converted
        ),
        advantage_lost=lost,
        advantage_restored=restored,
        comeback_team=comeback_team,
        max_t_advantage=max_t_advantage,
        max_ct_advantage=max_ct_advantage,
    )


def test_no_advantage():
    summary = make_summary(
        first_advantage_team=None,
        converted=None,
    )

    assert (
        classify_round_swing(summary)
        == "no_advantage"
    )


def test_clean_conversion():
    summary = make_summary(
        first_advantage_team=TEAM_CT,
        converted=True,
        lost=False,
        restored=False,
        max_t_advantage=0,
        max_ct_advantage=4,
    )

    assert not summary.advantage_reversed

    assert (
        classify_round_swing(summary)
        == "clean_conversion"
    )


def test_regained_after_only_returning_to_equal():
    summary = make_summary(
        first_advantage_team=TEAM_CT,
        converted=True,
        lost=True,
        restored=True,
        max_t_advantage=0,
        max_ct_advantage=2,
    )

    assert not summary.advantage_reversed

    assert (
        classify_round_swing(summary)
        == "regained"
    )


def test_comeback_requires_real_reversal():
    summary = make_summary(
        first_advantage_team=TEAM_CT,
        converted=True,
        lost=True,
        restored=True,
        comeback_team=TEAM_CT,
        max_t_advantage=1,
        max_ct_advantage=2,
    )

    assert summary.advantage_reversed

    assert (
        classify_round_swing(summary)
        == "comeback"
    )


def test_stolen_round():
    summary = make_summary(
        winner_team=TEAM_T,
        first_advantage_team=TEAM_CT,
        converted=False,
        lost=True,
        restored=False,
        comeback_team=TEAM_T,
        max_t_advantage=3,
        max_ct_advantage=1,
    )

    assert summary.advantage_reversed

    assert (
        classify_round_swing(summary)
        == "stolen"
    )


def test_real_swing():
    summary = make_summary(
        winner_team=TEAM_T,
        first_advantage_team=TEAM_CT,
        converted=False,
        lost=True,
        restored=True,
        comeback_team=TEAM_T,
        max_t_advantage=1,
        max_ct_advantage=1,
    )

    assert summary.advantage_reversed

    assert (
        classify_round_swing(summary)
        == "swing"
    )


def test_t_side_reversal_is_detected():
    summary = make_summary(
        winner_team=TEAM_T,
        first_advantage_team=TEAM_T,
        converted=True,
        lost=True,
        restored=True,
        comeback_team=TEAM_T,
        max_t_advantage=2,
        max_ct_advantage=1,
    )

    assert summary.advantage_reversed

    assert (
        classify_round_swing(summary)
        == "comeback"
    )

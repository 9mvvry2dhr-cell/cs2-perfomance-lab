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
        max_t_advantage=1,
        max_ct_advantage=1,
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
        winner_team=TEAM_CT,
        first_advantage_team=TEAM_CT,
        converted=True,
        lost=False,
        restored=False,
    )

    assert (
        classify_round_swing(summary)
        == "clean_conversion"
    )


def test_stolen_round():
    summary = make_summary(
        winner_team=TEAM_T,
        first_advantage_team=TEAM_CT,
        converted=False,
        lost=True,
        restored=False,
        comeback_team=TEAM_T,
    )

    assert (
        classify_round_swing(summary)
        == "stolen"
    )


def test_recovered_round():
    summary = make_summary(
        winner_team=TEAM_T,
        first_advantage_team=TEAM_T,
        converted=True,
        lost=True,
        restored=True,
        comeback_team=TEAM_T,
    )

    assert (
        classify_round_swing(summary)
        == "recovered"
    )


def test_swing_round():
    summary = make_summary(
        winner_team=TEAM_T,
        first_advantage_team=TEAM_CT,
        converted=False,
        lost=True,
        restored=True,
        comeback_team=TEAM_T,
    )

    assert (
        classify_round_swing(summary)
        == "swing"
    )


def test_initial_advantage_without_player_is_supported():
    summary = make_summary(
        winner_team=TEAM_CT,
        first_advantage_team=TEAM_CT,
        converted=True,
    )

    summary = RoundAdvantageSummary(
        round_num=summary.round_num,
        winner_team=summary.winner_team,
        first_advantage_team=(
            summary.first_advantage_team
        ),
        first_advantage_tick=100,
        first_advantage_by=None,
        converted_first_advantage=(
            summary.converted_first_advantage
        ),
        advantage_lost=False,
        advantage_restored=False,
        comeback_team=None,
        max_t_advantage=0,
        max_ct_advantage=1,
    )

    assert (
        classify_round_swing(summary)
        == "clean_conversion"
    )

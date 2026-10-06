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
from src.metrics.turning_story import (
    build_turning_round_stories,
)


def turn():
    return TurningRound(
        round_num=1,
        winner_team="team_a",
        swing_type="swing",
        score_a_before=6,
        score_b_before=6,
        score_a_after=7,
        score_b_after=6,
        opponent_streak_before=1,
        winner_run_length=4,
        reasons=(
            "strong_round_swing",
        ),
    )


def score(
    winner_side="CT",
):
    return RoundScoreState(
        round_num=1,
        winner_team="team_a",
        winner_side=winner_side,
        score_a_before=6,
        score_b_before=6,
        score_a_after=7,
        score_b_after=6,
    )


def tr(
    tick,
    *,
    t_before,
    ct_before,
    t_after,
    ct_after,
    attacker="a",
    victim="v",
    attacker_team=TEAM_CT,
    victim_team=TEAM_T,
):
    return RoundStateTransition(
        round_num=1,
        tick=tick,
        attacker=attacker,
        victim=victim,
        attacker_team=attacker_team,
        victim_team=victim_team,
        cause="enemy",
        t_alive_before=t_before,
        ct_alive_before=ct_before,
        t_alive_after=t_after,
        ct_alive_after=ct_after,
    )


def test_clean_control_first_gain_is_decisive():
    transitions = [
        tr(
            100,
            t_before=5,
            ct_before=5,
            t_after=4,
            ct_after=5,
        ),
        tr(
            200,
            t_before=4,
            ct_before=5,
            t_after=3,
            ct_after=5,
        ),
    ]

    stories = build_turning_round_stories(
        [turn()],
        [score()],
        transitions,
    )

    story = stories[0]

    assert story.decisive_tick == 100
    assert len(story.events) == 1

    assert (
        story.events[0].event_type
        == "control_gain"
    )

    assert story.events[0].decisive


def test_regained_round_uses_final_control_gain():
    transitions = [
        tr(
            100,
            t_before=5,
            ct_before=5,
            t_after=4,
            ct_after=5,
        ),
        tr(
            200,
            t_before=4,
            ct_before=5,
            t_after=4,
            ct_after=4,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
        tr(
            300,
            t_before=4,
            ct_before=4,
            t_after=3,
            ct_after=4,
        ),
        tr(
            400,
            t_before=3,
            ct_before=4,
            t_after=3,
            ct_after=3,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
        tr(
            500,
            t_before=3,
            ct_before=3,
            t_after=2,
            ct_after=3,
        ),
    ]

    story = build_turning_round_stories(
        [turn()],
        [score()],
        transitions,
    )[0]

    assert [
        event.event_type
        for event in story.events
    ] == [
        "control_gain",
        "control_loss",
        "control_gain",
        "control_loss",
        "control_gain",
    ]

    assert story.decisive_tick == 500

    decisive = [
        event
        for event in story.events
        if event.decisive
    ]

    assert len(decisive) == 1
    assert decisive[0].tick == 500


def test_swing_tracks_reversals_and_equalizers():
    transitions = [
        tr(
            100,
            t_before=5,
            ct_before=5,
            t_after=5,
            ct_after=4,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
        tr(
            110,
            t_before=5,
            ct_before=4,
            t_after=4,
            ct_after=4,
        ),
        tr(
            120,
            t_before=4,
            ct_before=4,
            t_after=4,
            ct_after=3,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
        tr(
            130,
            t_before=4,
            ct_before=3,
            t_after=3,
            ct_after=3,
        ),
        tr(
            140,
            t_before=3,
            ct_before=3,
            t_after=2,
            ct_after=3,
        ),
    ]

    story = build_turning_round_stories(
        [turn()],
        [score()],
        transitions,
    )[0]

    assert [
        event.event_type
        for event in story.events
    ] == [
        "reversal",
        "equalizer",
        "reversal",
        "equalizer",
        "control_gain",
    ]

    assert story.decisive_tick == 140
    assert story.events[-1].decisive


def test_objective_win_can_have_no_decisive_control():
    transitions = [
        tr(
            100,
            t_before=3,
            ct_before=3,
            t_after=3,
            ct_after=2,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
    ]

    story = build_turning_round_stories(
        [turn()],
        [score()],
        transitions,
    )[0]

    assert story.decisive_tick is None

    assert [
        event.event_type
        for event in story.events
    ] == [
        "reversal",
    ]

def test_final_duel_is_not_fake_decisive_control():
    transitions = [
        tr(
            100,
            t_before=1,
            ct_before=1,
            t_after=0,
            ct_after=1,
        ),
    ]

    story = build_turning_round_stories(
        [turn()],
        [score()],
        transitions,
    )[0]

    assert story.decisive_tick is None

    assert (
        story.resolution
        == "final_elimination"
    )

    assert len(story.events) == 1

    assert (
        story.events[0].event_type
        == "control_gain"
    )

    assert not story.events[0].decisive

def test_control_events_keep_source_transition_position():
    transitions = [
        # index 0: 0 -> +1, control event
        tr(
            100,
            t_before=5,
            ct_before=5,
            t_after=4,
            ct_after=5,
        ),
        # index 1: +1 -> +2, not a control event
        tr(
            200,
            t_before=4,
            ct_before=5,
            t_after=3,
            ct_after=5,
        ),
        # index 2: +2 -> +1, not a control event
        tr(
            300,
            t_before=3,
            ct_before=5,
            t_after=3,
            ct_after=4,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
        # index 3: +1 -> 0, control loss
        tr(
            400,
            t_before=3,
            ct_before=4,
            t_after=3,
            ct_after=3,
            attacker_team=TEAM_T,
            victim_team=TEAM_CT,
        ),
    ]

    story = build_turning_round_stories(
        [turn()],
        [score()],
        transitions,
    )[0]

    assert [
        event.event_type
        for event in story.events
    ] == [
        "control_gain",
        "control_loss",
    ]

    assert [
        event.round_state_position
        for event in story.events
    ] == [
        0,
        3,
    ]

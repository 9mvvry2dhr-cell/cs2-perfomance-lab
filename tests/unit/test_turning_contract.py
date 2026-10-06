from src.domain.analysis import (
    build_match_analysis,
)
from src.metrics.match_flow import (
    RoundScoreState,
)
from src.metrics.round_state import (
    TEAM_CT,
)
from src.metrics.turning_round import (
    TurningRound,
)
from src.metrics.turning_story import (
    TurningRoundStory,
)
from src.parsing.dto import (
    ParsedMatch,
)


def test_turning_analysis_flows_into_match_analysis():
    flow = RoundScoreState(
        round_num=13,
        winner_team="team_a",
        winner_side="CT",
        score_a_before=6,
        score_b_before=6,
        score_a_after=7,
        score_b_after=6,
    )

    turning = TurningRound(
        round_num=13,
        winner_team="team_a",
        swing_type="swing",
        score_a_before=6,
        score_b_before=6,
        score_a_after=7,
        score_b_after=6,
        opponent_streak_before=1,
        winner_run_length=4,
        reasons=(
            "took_lead",
            "strong_round_swing",
        ),
    )

    story = TurningRoundStory(
        round_num=13,
        winner_team_num=TEAM_CT,
        events=(),
        decisive_tick=93618,
        resolution="sustained_control",
    )

    parsed = ParsedMatch(
        match_id="match-1",
        map_name="de_anubis",
        duration_seconds=1200,
        rounds_played=20,
        score_ct=13,
        score_t=7,
        winner_side="CT",
        players=[],
        rounds=[],
        match_flow=[flow],
        turning_rounds=[turning],
        turning_stories=[story],
    )

    analysis = build_match_analysis(
        parsed,
        {},
    )

    assert analysis.match_flow == [
        flow
    ]

    assert analysis.turning_rounds == [
        turning
    ]

    assert analysis.turning_stories == [
        story
    ]

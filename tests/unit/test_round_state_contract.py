import unittest

from src.domain.analysis import (
    build_match_analysis,
)
from src.metrics.round_state import (
    RoundAdvantageSummary,
    RoundStateTransition,
    TEAM_CT,
    TEAM_T,
)
from src.parsing.dto import (
    ParsedMatch,
    ParsedPlayer,
    ParsedRound,
)


class TestRoundStateAnalysisContract(
    unittest.TestCase
):

    def test_round_state_survives_analysis_build(
        self,
    ):
        transition = (
            RoundStateTransition(
                round_num=1,
                tick=300,
                attacker="CT1",
                victim="T1",
                attacker_team=TEAM_CT,
                victim_team=TEAM_T,
                cause="enemy",
                t_alive_before=5,
                ct_alive_before=5,
                t_alive_after=4,
                ct_alive_after=5,
            )
        )

        advantage = (
            RoundAdvantageSummary(
                round_num=1,
                winner_team=TEAM_CT,
                first_advantage_team=TEAM_CT,
                first_advantage_tick=300,
                first_advantage_by="CT1",
                converted_first_advantage=True,
                advantage_lost=False,
                advantage_restored=False,
                comeback_team=None,
                max_t_advantage=0,
                max_ct_advantage=1,
            )
        )

        player = ParsedPlayer(
            steam_id="CT1",
            name="Player",
            kills=1,
            deaths=0,
            assists=0,
            damage=100.0,
            headshots=1,
            rounds_played=1,
        )

        match = ParsedMatch(
            match_id="test",
            map_name="de_mirage",
            duration_seconds=90,
            rounds_played=1,
            score_ct=1,
            score_t=0,
            winner_side="CT",
            players=[
                player,
            ],
            rounds=[
                ParsedRound(
                    round_num=1,
                    winner_side="CT",
                    win_reason="test",
                    end_tick=900,
                )
            ],
            player_results={
                "CT1": "win",
            },
            round_state_transitions=[
                transition,
            ],
            round_advantage=[
                advantage,
            ],
        )

        analysis = build_match_analysis(
            match,
            {
                "CT1": {},
            },
        )

        self.assertEqual(
            analysis.round_state_transitions,
            [
                transition,
            ],
        )

        self.assertEqual(
            analysis.round_advantage,
            [
                advantage,
            ],
        )

        self.assertEqual(
            analysis.round_advantage[
                0
            ].first_advantage_by,
            "CT1",
        )


if __name__ == "__main__":
    unittest.main()

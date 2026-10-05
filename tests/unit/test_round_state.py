import unittest

import pandas as pd

from src.metrics.round_state import (
    TEAM_CT,
    TEAM_T,
    build_round_state_transitions,
    summarize_round_advantage,
)


class FakeDemoParser:
    def __init__(
        self,
        *,
        deaths,
        tick_rows,
        winner="CT",
    ):
        self.deaths = deaths
        self.tick_rows = tick_rows
        self.winner = winner

    def parse_events(
        self,
        event_names,
    ):
        event_name = (
            event_names[0]
        )

        if event_name == "round_start":
            return pd.DataFrame(
                {
                    "tick": [
                        100,
                    ],
                }
            )

        if (
            event_name
            == "round_freeze_end"
        ):
            return pd.DataFrame(
                {
                    "tick": [
                        200,
                    ],
                }
            )

        if event_name == "round_end":
            return pd.DataFrame(
                [
                    {
                        "tick": 900,
                        "winner": (
                            self.winner
                        ),
                    }
                ]
            )

        if (
            event_name
            == "cs_win_panel_match"
        ):
            return pd.DataFrame()

        if (
            event_name
            == "begin_new_match"
        ):
            return pd.DataFrame()

        return pd.DataFrame()

    def parse_event(
        self,
        event_name,
        player=None,
        other=None,
    ):
        if (
            event_name
            == "player_death"
        ):
            return pd.DataFrame(
                self.deaths
            )

        return pd.DataFrame()

    def parse_ticks(
        self,
        fields,
        ticks=None,
    ):
        wanted = set(
            ticks or []
        )

        return pd.DataFrame([
            row
            for row
            in self.tick_rows
            if row[
                "tick"
            ] in wanted
        ])


def roster_rows():
    rows = []

    for index in range(5):
        rows.append(
            {
                "tick": 200,
                "steamid": (
                    f"T{index + 1}"
                ),
                "team_num": TEAM_T,
                "health": 100,
            }
        )

        rows.append(
            {
                "tick": 200,
                "steamid": (
                    f"C{index + 1}"
                ),
                "team_num": TEAM_CT,
                "health": 100,
            }
        )

    return rows


class TestRoundStateEngine(
    unittest.TestCase
):

    def test_enemy_kill_creates_5v4(
        self,
    ):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "C1",
                    "user_steamid": "T1",
                },
            ],
            tick_rows=roster_rows(),
            winner="CT",
        )

        transitions = (
            build_round_state_transitions(
                parser
            )
        )

        self.assertEqual(
            len(transitions),
            1,
        )

        transition = (
            transitions[0]
        )

        self.assertEqual(
            transition.state_before,
            "T5-CT5",
        )

        self.assertEqual(
            transition.state_after,
            "T4-CT5",
        )

        self.assertEqual(
            transition.cause,
            "enemy",
        )

        summary = (
            summarize_round_advantage(
                parser,
                transitions=transitions,
            )[0]
        )

        self.assertEqual(
            summary.first_advantage_team,
            TEAM_CT,
        )

        self.assertEqual(
            summary.first_advantage_by,
            "C1",
        )

        self.assertTrue(
            summary.converted_first_advantage
        )

        self.assertFalse(
            summary.advantage_lost
        )

        self.assertEqual(
            summary.max_ct_advantage,
            1,
        )


    def test_advantage_can_be_lost_and_restored(
        self,
    ):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "C1",
                    "user_steamid": "T1",
                },
                {
                    "tick": 350,
                    "attacker_steamid": "T2",
                    "user_steamid": "C1",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "C2",
                    "user_steamid": "T2",
                },
            ],
            tick_rows=roster_rows(),
            winner="CT",
        )

        summary = (
            summarize_round_advantage(
                parser
            )[0]
        )

        self.assertEqual(
            summary.first_advantage_team,
            TEAM_CT,
        )

        self.assertTrue(
            summary.advantage_lost
        )

        self.assertTrue(
            summary.advantage_restored
        )

        self.assertTrue(
            summary.converted_first_advantage
        )


    def test_round_winner_can_comeback(
        self,
    ):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "C1",
                    "user_steamid": "T1",
                },
                {
                    "tick": 350,
                    "attacker_steamid": "T2",
                    "user_steamid": "C1",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "T3",
                    "user_steamid": "C2",
                },
            ],
            tick_rows=roster_rows(),
            winner="T",
        )

        summary = (
            summarize_round_advantage(
                parser
            )[0]
        )

        self.assertEqual(
            summary.first_advantage_team,
            TEAM_CT,
        )

        self.assertFalse(
            summary.converted_first_advantage
        )

        self.assertTrue(
            summary.advantage_lost
        )

        self.assertEqual(
            summary.comeback_team,
            TEAM_T,
        )


    def test_teamkill_changes_alive_state_but_has_no_creator(
        self,
    ):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "C1",
                    "user_steamid": "C2",
                },
            ],
            tick_rows=roster_rows(),
            winner="T",
        )

        transitions = (
            build_round_state_transitions(
                parser
            )
        )

        self.assertEqual(
            len(transitions),
            1,
        )

        self.assertEqual(
            transitions[0].cause,
            "teamkill",
        )

        self.assertEqual(
            transitions[0].state_after,
            "T5-CT4",
        )

        summary = (
            summarize_round_advantage(
                parser,
                transitions=transitions,
            )[0]
        )

        self.assertEqual(
            summary.first_advantage_team,
            TEAM_T,
        )

        self.assertIsNone(
            summary.first_advantage_by
        )


    def test_duplicate_victim_death_is_ignored(
        self,
    ):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "C1",
                    "user_steamid": "T1",
                },
                {
                    "tick": 310,
                    "attacker_steamid": "C2",
                    "user_steamid": "T1",
                },
            ],
            tick_rows=roster_rows(),
            winner="CT",
        )

        transitions = (
            build_round_state_transitions(
                parser
            )
        )

        self.assertEqual(
            len(transitions),
            1,
        )




def short_roster_rows():
    rows = []

    for index in range(4):
        rows.append(
            {
                "tick": 200,
                "steamid": f"T{index + 1}",
                "team_num": TEAM_T,
                "health": 100,
            }
        )

    for index in range(5):
        rows.append(
            {
                "tick": 200,
                "steamid": f"C{index + 1}",
                "team_num": TEAM_CT,
                "health": 100,
            }
        )

    return rows


class TestInitialRoundAdvantage(
    unittest.TestCase
):

    def test_initial_4v5_is_advantage(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "T1",
                    "user_steamid": "C1",
                },
                {
                    "tick": 350,
                    "attacker_steamid": "T2",
                    "user_steamid": "C2",
                },
            ],
            tick_rows=short_roster_rows(),
            winner="T",
        )

        summary = (
            summarize_round_advantage(
                parser
            )[0]
        )

        self.assertEqual(
            summary.first_advantage_team,
            TEAM_CT,
        )

        self.assertEqual(
            summary.first_advantage_tick,
            200,
        )

        self.assertIsNone(
            summary.first_advantage_by
        )

        self.assertTrue(
            summary.advantage_lost
        )

        self.assertEqual(
            summary.comeback_team,
            TEAM_T,
        )

        self.assertEqual(
            summary.max_ct_advantage,
            1,
        )

        self.assertEqual(
            summary.max_t_advantage,
            1,
        )


if __name__ == "__main__":
    unittest.main()

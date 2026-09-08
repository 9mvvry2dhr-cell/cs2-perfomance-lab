import unittest

import pandas as pd

from src.metrics.clutch import calculate_clutches


class FakeDemoParser:

    def __init__(
        self,
        deaths=None,
        team_rows=None,
        starts=None,
        freezes=None,
        ends=None,
        panel_ticks=None,
    ):
        self.deaths = deaths or []
        self.team_rows = team_rows or []

        self.starts = (
            starts
            if starts is not None
            else [100]
        )

        self.freezes = (
            freezes
            if freezes is not None
            else [150]
        )

        self.ends = (
            ends
            if ends is not None
            else [
                {
                    "tick": 900,
                    "winner": "T",
                }
            ]
        )

        self.panel_ticks = (
            panel_ticks
            if panel_ticks is not None
            else []
        )

    def parse_events(
        self,
        event_names,
    ):
        event_name = event_names[0]

        if event_name == "round_start":
            return pd.DataFrame(
                {
                    "tick": self.starts,
                }
            )

        if event_name == "round_freeze_end":
            return pd.DataFrame(
                {
                    "tick": self.freezes,
                }
            )

        if event_name == "round_end":
            return pd.DataFrame(
                self.ends
            )

        if event_name == "cs_win_panel_match":
            return pd.DataFrame(
                {
                    "tick": self.panel_ticks,
                }
            )

        if event_name == "player_death":
            return pd.DataFrame(
                self.deaths
            )

        return pd.DataFrame()

    def parse_ticks(
        self,
        fields,
        ticks=None,
    ):
        wanted_ticks = set(
            ticks or []
        )

        rows = [
            row
            for row in self.team_rows
            if row["tick"] in wanted_ticks
        ]

        return pd.DataFrame(
            rows
        )


class TestClutchMetrics(unittest.TestCase):

    def test_wins_one_vs_one(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B2",
                    "team_num": 3,
                },
            ],
            deaths=[
                # First reduce enemy side to one player.
                {
                    "tick": 250,
                    "attacker_steamid": "A",
                    "user_steamid": "B2",
                },
                # A now becomes sole survivor: 1v1.
                {
                    "tick": 300,
                    "attacker_steamid": "B",
                    "user_steamid": "A2",
                },
                # A wins the duel and survives.
                {
                    "tick": 350,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
                "B2",
            ],
        )

        self.assertEqual(
            clutches["A"],
            1,
        )

    def test_one_vs_three_is_counted_only_once(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B2",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B3",
                    "team_num": 3,
                },
            ],
            deaths=[
                # A becomes 1v3 here.
                {
                    "tick": 200,
                    "attacker_steamid": "B",
                    "user_steamid": "A2",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "B2",
                },
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "B3",
                },
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
                "B2",
                "B3",
            ],
        )

        self.assertEqual(
            clutches["A"],
            1,
        )

    def test_losing_clutch_is_not_counted(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B2",
                    "team_num": 3,
                },
            ],
            deaths=[
                # A becomes 1v2.
                {
                    "tick": 300,
                    "attacker_steamid": "B",
                    "user_steamid": "A2",
                },
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                }
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
                "B2",
            ],
        )

        self.assertEqual(
            clutches["A"],
            0,
        )

    def test_clutch_player_must_survive_round_end(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B2",
                    "team_num": 3,
                },
            ],
            deaths=[
                # A becomes a clutch candidate.
                {
                    "tick": 250,
                    "attacker_steamid": "B",
                    "user_steamid": "A2",
                },
                # But A dies before round_end.
                {
                    "tick": 500,
                    "attacker_steamid": "B",
                    "user_steamid": "A",
                },
            ],
            ends=[
                # Team 2 may still win by objective,
                # but A did not survive.
                {
                    "tick": 900,
                    "winner": "T",
                }
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
                "B2",
            ],
        )

        self.assertEqual(
            clutches["A"],
            0,
        )

    def test_teamkill_and_suicide_update_alive_state(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B2",
                    "team_num": 3,
                },
            ],
            deaths=[
                # Teamkill: A2 is still dead afterwards.
                {
                    "tick": 200,
                    "attacker_steamid": "A",
                    "user_steamid": "A2",
                },
                # Suicide: B is also removed from alive state.
                {
                    "tick": 300,
                    "attacker_steamid": "B",
                    "user_steamid": "B",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "B2",
                },
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
                "B2",
            ],
        )

        self.assertEqual(
            clutches["A"],
            1,
        )

    def test_missing_team_roster_is_not_guessed(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                # No valid team 3 roster.
            ],
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "A2",
                },
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
            ],
        )

        self.assertEqual(
            clutches["A"],
            0,
        )

    def test_side_change_between_rounds_is_supported(self):
        parser = FakeDemoParser(
            starts=[
                100,
                1000,
            ],
            freezes=[
                150,
                1050,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "T",
                },
                {
                    "tick": 1900,
                    "winner": "CT",
                },
            ],
            team_rows=[
                # Round 1: A is T.
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "A2",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "B2",
                    "team_num": 3,
                },

                # Round 2: sides swapped.
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1050,
                    "steamid": "A2",
                    "team_num": 3,
                },
                {
                    "tick": 1050,
                    "steamid": "B",
                    "team_num": 2,
                },
                {
                    "tick": 1050,
                    "steamid": "B2",
                    "team_num": 2,
                },
            ],
            deaths=[
                # Round 1: A wins 1v1.
                {
                    "tick": 200,
                    "attacker_steamid": "A",
                    "user_steamid": "B2",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "B",
                    "user_steamid": "A2",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },

                # Round 2: A wins another 1v1 after side swap.
                {
                    "tick": 1200,
                    "attacker_steamid": "A",
                    "user_steamid": "B2",
                },
                {
                    "tick": 1300,
                    "attacker_steamid": "B",
                    "user_steamid": "A2",
                },
                {
                    "tick": 1400,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
        )

        clutches = calculate_clutches(
            parser,
            [
                "A",
                "A2",
                "B",
                "B2",
            ],
        )

        self.assertEqual(
            clutches["A"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
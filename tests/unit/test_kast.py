import unittest

import pandas as pd

from src.metrics.kast import calculate_kast_metrics


class FakeDemoParser:
    def __init__(
        self,
        deaths,
        team_rows,
        starts=None,
        freezes=None,
        ends=None,
        panel_ticks=None,
    ):
        self.deaths = deaths
        self.team_rows = team_rows

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
                    "winner": "CT",
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
                {"tick": self.starts}
            )

        if event_name == "round_freeze_end":
            return pd.DataFrame(
                {"tick": self.freezes}
            )

        if event_name == "round_end":
            return pd.DataFrame(
                self.ends
            )

        if event_name == "cs_win_panel_match":
            return pd.DataFrame(
                {"tick": self.panel_ticks}
            )

        if event_name == "player_death":
            return pd.DataFrame(
                self.deaths
            )

        return pd.DataFrame()

    def parse_event(
        self,
        event_name,
        player=None,
        other=None,
    ):
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

        return pd.DataFrame([
            row
            for row in self.team_rows
            if row["tick"] in wanted_ticks
        ])


class TestKASTMetrics(unittest.TestCase):

    def test_kill_makes_round_kast_positive(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                    "assister_steamid": "",
                },
                {
                    "tick": 700,
                    "game_time": 20.0,
                    "attacker_steamid": "Y",
                    "user_steamid": "A",
                    "assister_steamid": "",
                },
            ],
            team_rows=[
                {"tick": 150, "steamid": "A", "team_num": 2},
                {"tick": 150, "steamid": "B", "team_num": 2},
                {"tick": 150, "steamid": "X", "team_num": 3},
                {"tick": 150, "steamid": "Y", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 700, "steamid": "Y", "team_num": 3},
                {"tick": 700, "steamid": "A", "team_num": 2},
            ],
        )

        stats = calculate_kast_metrics(
            parser,
            ["A", "B", "X", "Y"],
        )

        self.assertEqual(
            stats["A"],
            1,
        )

    def test_assist_makes_round_kast_positive(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                    "assister_steamid": "A",
                },
                {
                    "tick": 700,
                    "game_time": 20.0,
                    "attacker_steamid": "Y",
                    "user_steamid": "A",
                    "assister_steamid": "",
                },
            ],
            team_rows=[
                {"tick": 150, "steamid": "A", "team_num": 2},
                {"tick": 150, "steamid": "B", "team_num": 2},
                {"tick": 150, "steamid": "X", "team_num": 3},
                {"tick": 150, "steamid": "Y", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "B", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 700, "steamid": "Y", "team_num": 3},
                {"tick": 700, "steamid": "A", "team_num": 2},
            ],
        )

        stats = calculate_kast_metrics(
            parser,
            ["A", "B", "X", "Y"],
        )

        self.assertEqual(
            stats["A"],
            1,
        )

    def test_survival_makes_round_kast_positive(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "B",
                    "assister_steamid": "",
                }
            ],
            team_rows=[
                {"tick": 150, "steamid": "A", "team_num": 2},
                {"tick": 150, "steamid": "B", "team_num": 2},
                {"tick": 150, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "B", "team_num": 2},
            ],
        )

        stats = calculate_kast_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(
            stats["A"],
            1,
        )

        self.assertEqual(
            stats["B"],
            0,
        )

    def test_traded_death_makes_round_kast_positive(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                    "assister_steamid": "",
                },
                {
                    "tick": 400,
                    "game_time": 12.0,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                    "assister_steamid": "",
                },
            ],
            team_rows=[
                {"tick": 150, "steamid": "A", "team_num": 2},
                {"tick": 150, "steamid": "B", "team_num": 2},
                {"tick": 150, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "B", "team_num": 2},
                {"tick": 400, "steamid": "X", "team_num": 3},
            ],
        )

        stats = calculate_kast_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(
            stats["A"],
            1,
        )

    def test_multiple_conditions_count_round_only_once(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                    "assister_steamid": "",
                }
            ],
            team_rows=[
                {"tick": 150, "steamid": "A", "team_num": 2},
                {"tick": 150, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
            ],
        )

        stats = calculate_kast_metrics(
            parser,
            ["A", "X"],
        )

        # A has both K and S, but the round counts once.
        self.assertEqual(
            stats["A"],
            1,
        )

    def test_teamkill_or_suicide_removes_survival(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "assister_steamid": "",
                },
                {
                    "tick": 400,
                    "game_time": 12.0,
                    "attacker_steamid": "C",
                    "user_steamid": "C",
                    "assister_steamid": "",
                },
            ],
            team_rows=[
                {"tick": 150, "steamid": "A", "team_num": 2},
                {"tick": 150, "steamid": "B", "team_num": 2},
                {"tick": 150, "steamid": "C", "team_num": 3},
                {"tick": 150, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "B", "team_num": 2},
                {"tick": 400, "steamid": "C", "team_num": 3},
            ],
        )

        stats = calculate_kast_metrics(
            parser,
            ["A", "B", "C", "X"],
        )

        # B died from a teamkill and C suicided.
        # Neither death may count as S or T.
        self.assertEqual(
            stats["B"],
            0,
        )

        self.assertEqual(
            stats["C"],
            0,
        )


if __name__ == "__main__":
    unittest.main()

import unittest

import pandas as pd

from src.metrics.trade import calculate_trade_metrics


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


class TestTradeMetrics(unittest.TestCase):

    def test_trade_within_window_counts(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                },
                {
                    "tick": 400,
                    "game_time": 14.5,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "B", "team_num": 2},
                {"tick": 400, "steamid": "X", "team_num": 3},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(traded_deaths["A"], 1)
        self.assertEqual(trade_kills["B"], 1)

    def test_exact_window_boundary_counts(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                },
                {
                    "tick": 400,
                    "game_time": 15.0,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "B", "team_num": 2},
                {"tick": 400, "steamid": "X", "team_num": 3},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(traded_deaths["A"], 1)
        self.assertEqual(trade_kills["B"], 1)

    def test_after_window_does_not_count(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                },
                {
                    "tick": 400,
                    "game_time": 15.01,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "B", "team_num": 2},
                {"tick": 400, "steamid": "X", "team_num": 3},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(traded_deaths["A"], 0)
        self.assertEqual(trade_kills["B"], 0)

    def test_teamkill_and_suicide_are_ignored(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 250,
                    "game_time": 10.0,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                },
                {
                    "tick": 300,
                    "game_time": 11.0,
                    "attacker_steamid": "C",
                    "user_steamid": "D",
                },
            ],
            team_rows=[
                {"tick": 250, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "C", "team_num": 2},
                {"tick": 300, "steamid": "D", "team_num": 2},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "C", "D"],
        )

        self.assertEqual(sum(trade_kills.values()), 0)
        self.assertEqual(sum(traded_deaths.values()), 0)

    def test_trade_does_not_cross_round_boundary(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 490,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                },
                {
                    "tick": 610,
                    "game_time": 11.0,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                },
            ],
            team_rows=[
                {"tick": 490, "steamid": "X", "team_num": 3},
                {"tick": 490, "steamid": "A", "team_num": 2},
                {"tick": 610, "steamid": "B", "team_num": 2},
                {"tick": 610, "steamid": "X", "team_num": 3},
            ],
            starts=[100, 600],
            freezes=[150, 650],
            ends=[
                {"tick": 500, "winner": "CT"},
                {"tick": 1000, "winner": "T"},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(traded_deaths["A"], 0)
        self.assertEqual(trade_kills["B"], 0)

    def test_unknown_team_relation_is_ignored(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                },
                {
                    "tick": 400,
                    "game_time": 12.0,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 400, "steamid": "B", "team_num": 2},
                {"tick": 400, "steamid": "X", "team_num": 3},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(traded_deaths["A"], 0)
        self.assertEqual(trade_kills["B"], 0)

    def test_one_retaliation_can_trade_multiple_deaths_but_is_one_trade_kill(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                },
                {
                    "tick": 320,
                    "game_time": 12.0,
                    "attacker_steamid": "X",
                    "user_steamid": "C",
                },
                {
                    "tick": 340,
                    "game_time": 14.0,
                    "attacker_steamid": "B",
                    "user_steamid": "X",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 320, "steamid": "X", "team_num": 3},
                {"tick": 320, "steamid": "C", "team_num": 2},
                {"tick": 340, "steamid": "B", "team_num": 2},
                {"tick": 340, "steamid": "X", "team_num": 3},
            ],
        )

        trade_kills, traded_deaths = calculate_trade_metrics(
            parser,
            ["A", "B", "C", "X"],
        )

        self.assertEqual(traded_deaths["A"], 1)
        self.assertEqual(traded_deaths["C"], 1)
        self.assertEqual(trade_kills["B"], 1)


if __name__ == "__main__":
    unittest.main()

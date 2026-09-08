import unittest

import pandas as pd

from src.metrics.survival import (
    calculate_survival_metrics,
    detect_survival_rounds,
)


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


class TestSurvivalMetrics(unittest.TestCase):

    def test_player_survives_round(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "X",
                    "user_steamid": "B",
                }
            ],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "X",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_survival_metrics(
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

    def test_enemy_death_breaks_survival(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                }
            ],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "X",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_survival_metrics(
            parser,
            ["A", "X"],
        )

        self.assertEqual(
            stats["A"],
            0,
        )

    def test_teamkill_breaks_survival(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "B",
                    "user_steamid": "A",
                }
            ],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 2,
                },
            ],
        )

        stats = calculate_survival_metrics(
            parser,
            ["A", "B"],
        )

        self.assertEqual(
            stats["A"],
            0,
        )

    def test_suicide_breaks_survival(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                }
            ],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
            ],
        )

        stats = calculate_survival_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"],
            0,
        )

    def test_player_not_in_freeze_end_roster_is_not_counted(self):
        parser = FakeDemoParser(
            deaths=[],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "X",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_survival_metrics(
            parser,
            ["A", "B", "X"],
        )

        self.assertEqual(
            stats["A"],
            0,
        )

        self.assertEqual(
            stats["B"],
            1,
        )

    def test_survival_across_rounds_with_side_change(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "X",
                    "user_steamid": "A",
                }
            ],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "X",
                    "team_num": 3,
                },
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1050,
                    "steamid": "X",
                    "team_num": 2,
                },
            ],
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
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
            ],
        )

        stats = calculate_survival_metrics(
            parser,
            ["A", "X"],
        )

        self.assertEqual(
            stats["A"],
            1,
        )

    def test_round_level_api_exposes_survival(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "X",
                    "user_steamid": "B",
                }
            ],
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 2,
                },
            ],
        )

        events = detect_survival_rounds(
            parser,
            ["A", "B"],
        )

        self.assertEqual(
            len(events),
            1,
        )

        self.assertEqual(
            events[0].round_num,
            1,
        )

        self.assertEqual(
            events[0].steam_id,
            "A",
        )


if __name__ == "__main__":
    unittest.main()

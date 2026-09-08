import unittest

import pandas as pd

from src.metrics.multikill import (
    calculate_multikill_metrics,
    detect_multikill_rounds,
)


class FakeDemoParser:
    def __init__(
        self,
        deaths,
        team_rows,
        starts=None,
        freezes=None,
        ends=None,
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
            return pd.DataFrame()

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


class TestMultikillMetrics(unittest.TestCase):

    def test_exact_two_k_round(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "Y",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 400, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "Y", "team_num": 3},
            ],
        )

        stats = calculate_multikill_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["two_k_rounds"],
            1,
        )
        self.assertEqual(
            stats["A"]["three_k_rounds"],
            0,
        )

    def test_exact_three_k_round_is_exclusive(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "Y",
                },
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "Z",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 400, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "Y", "team_num": 3},
                {"tick": 500, "steamid": "A", "team_num": 2},
                {"tick": 500, "steamid": "Z", "team_num": 3},
            ],
        )

        stats = calculate_multikill_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["two_k_rounds"],
            0,
        )
        self.assertEqual(
            stats["A"]["three_k_rounds"],
            1,
        )

    def test_exact_four_k_round(self):
        deaths = []
        team_rows = []

        for index, victim in enumerate(
            ["W", "X", "Y", "Z"],
            start=1,
        ):
            tick = 200 + index * 100

            deaths.append(
                {
                    "tick": tick,
                    "attacker_steamid": "A",
                    "user_steamid": victim,
                }
            )

            team_rows.extend([
                {
                    "tick": tick,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": tick,
                    "steamid": victim,
                    "team_num": 3,
                },
            ])

        parser = FakeDemoParser(
            deaths=deaths,
            team_rows=team_rows,
        )

        stats = calculate_multikill_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["four_k_rounds"],
            1,
        )

    def test_exact_five_k_round(self):
        deaths = []
        team_rows = []

        for index, victim in enumerate(
            ["V", "W", "X", "Y", "Z"],
            start=1,
        ):
            tick = 200 + index * 100

            deaths.append(
                {
                    "tick": tick,
                    "attacker_steamid": "A",
                    "user_steamid": victim,
                }
            )

            team_rows.extend([
                {
                    "tick": tick,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": tick,
                    "steamid": victim,
                    "team_num": 3,
                },
            ])

        parser = FakeDemoParser(
            deaths=deaths,
            team_rows=team_rows,
        )

        stats = calculate_multikill_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["five_k_rounds"],
            1,
        )

    def test_teamkill_suicide_and_unknown_do_not_count(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                },
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                },
                {
                    "tick": 600,
                    "attacker_steamid": "A",
                    "user_steamid": "Y",
                },
            ],
            team_rows=[
                # Teamkill
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "B", "team_num": 2},

                # Suicide
                {"tick": 400, "steamid": "A", "team_num": 2},

                # Unknown relation: victim team missing
                {"tick": 500, "steamid": "A", "team_num": 2},

                # One valid enemy kill only
                {"tick": 600, "steamid": "A", "team_num": 2},
                {"tick": 600, "steamid": "Y", "team_num": 3},
            ],
        )

        events = detect_multikill_rounds(
            parser
        )

        self.assertEqual(
            events,
            [],
        )

    def test_kills_from_different_rounds_do_not_combine(self):
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
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
            ],
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                },
                {
                    "tick": 1300,
                    "attacker_steamid": "A",
                    "user_steamid": "Y",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 1300, "steamid": "A", "team_num": 3},
                {"tick": 1300, "steamid": "Y", "team_num": 2},
            ],
        )

        events = detect_multikill_rounds(
            parser
        )

        self.assertEqual(
            events,
            [],
        )

    def test_round_level_api_exposes_round_and_kill_count(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "Y",
                },
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "Z",
                },
            ],
            team_rows=[
                {"tick": 300, "steamid": "A", "team_num": 2},
                {"tick": 300, "steamid": "X", "team_num": 3},
                {"tick": 400, "steamid": "A", "team_num": 2},
                {"tick": 400, "steamid": "Y", "team_num": 3},
                {"tick": 500, "steamid": "A", "team_num": 2},
                {"tick": 500, "steamid": "Z", "team_num": 3},
            ],
        )

        events = detect_multikill_rounds(
            parser
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

        self.assertEqual(
            events[0].kills,
            3,
        )


if __name__ == "__main__":
    unittest.main()

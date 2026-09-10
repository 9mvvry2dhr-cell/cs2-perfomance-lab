import unittest

import pandas as pd

from src.metrics.entry import (
    calculate_entry_metrics,
    detect_entry_events,
)


class FakeDemoParser:
    """
    Минимальный parser для unit-тестов Entry.
    """

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

    def parse_events(self, event_names):
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


class TestEntryMetrics(unittest.TestCase):

    def test_first_enemy_kill_is_entry(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                }
            ],
            team_rows=[
                {
                    "tick": 300,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "B",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_entry_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["entry_kills"],
            1,
        )

        self.assertEqual(
            stats["A"]["entry_deaths"],
            0,
        )

        self.assertEqual(
            stats["B"]["entry_kills"],
            0,
        )

        self.assertEqual(
            stats["B"]["entry_deaths"],
            1,
        )

    def test_teamkill_before_enemy_kill_is_skipped(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 250,
                    "attacker_steamid": "A",
                    "user_steamid": "C",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
            team_rows=[
                {
                    "tick": 250,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 250,
                    "steamid": "C",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "B",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_entry_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["entry_kills"],
            1,
        )

        self.assertEqual(
            stats["B"]["entry_deaths"],
            1,
        )

        self.assertNotIn(
            "C",
            stats,
        )

    def test_suicide_before_enemy_kill_is_skipped(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 250,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "C",
                    "user_steamid": "B",
                },
            ],
            team_rows=[
                {
                    "tick": 300,
                    "steamid": "C",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "B",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_entry_metrics(
            parser
        )

        self.assertEqual(
            stats["C"]["entry_kills"],
            1,
        )

        self.assertEqual(
            stats["B"]["entry_deaths"],
            1,
        )

        self.assertNotIn(
            "A",
            stats,
        )

    def test_unknown_team_relation_blocks_round(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 250,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "C",
                    "user_steamid": "D",
                },
            ],
            team_rows=[
                # B отсутствует -> первая relation unknown.
                {
                    "tick": 250,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "C",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "D",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_entry_metrics(
            parser
        )

        self.assertEqual(
            stats,
            {},
        )

    def test_death_outside_round_is_ignored(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 50,
                    "attacker_steamid": "X",
                    "user_steamid": "Y",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
            team_rows=[
                {
                    "tick": 300,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "B",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_entry_metrics(
            parser
        )

        self.assertNotIn(
            "X",
            stats,
        )

        self.assertNotIn(
            "Y",
            stats,
        )

        self.assertEqual(
            stats["A"]["entry_kills"],
            1,
        )

        self.assertEqual(
            stats["B"]["entry_deaths"],
            1,
        )

    def test_same_tick_preserves_event_order(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
                {
                    "tick": 300,
                    "attacker_steamid": "C",
                    "user_steamid": "D",
                },
            ],
            team_rows=[
                {
                    "tick": 300,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "B",
                    "team_num": 3,
                },
                {
                    "tick": 300,
                    "steamid": "C",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "D",
                    "team_num": 3,
                },
            ],
        )

        stats = calculate_entry_metrics(
            parser
        )

        # При одинаковом tick первое событие
        # в исходном порядке остаётся opening kill.
        self.assertEqual(
            stats["A"]["entry_kills"],
            1,
        )

        self.assertEqual(
            stats["B"]["entry_deaths"],
            1,
        )

        self.assertNotIn(
            "C",
            stats,
        )

        self.assertNotIn(
            "D",
            stats,
        )



    def test_round_level_entry_event_is_exposed(self):
        parser = FakeDemoParser(
            deaths=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
            team_rows=[
                {
                    "tick": 300,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "B",
                    "team_num": 3,
                },
            ],
        )

        events = detect_entry_events(
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
            events[0].attacker,
            "A",
        )

        self.assertEqual(
            events[0].victim,
            "B",
        )

        self.assertEqual(
            events[0].tick,
            300,
        )


if __name__ == "__main__":
    unittest.main()
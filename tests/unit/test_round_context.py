import unittest

import pandas as pd

from src.metrics.round_context import (
    build_round_contexts,
    find_round,
    normalize_team_num,
)


class FakeDemoParser:
    """
    Минимальный fake demoparser2 для unit-тестов.

    Нам не нужна настоящая .dem:
    мы сами задаём round_start / freeze_end / round_end.
    """

    def __init__(
        self,
        starts=None,
        freezes=None,
        ends=None,
        panel_ticks=None,
    ):
        self.starts = starts or []
        self.freezes = freezes or []
        self.ends = ends or []
        self.panel_ticks = panel_ticks or []

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

        return pd.DataFrame()


class TestRoundContext(unittest.TestCase):

    def test_builds_normal_rounds(self):
        parser = FakeDemoParser(
            starts=[
                100,
                1000,
            ],
            freezes=[
                200,
                1100,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1900,
                    "winner": "T",
                },
            ],
        )

        rounds = build_round_contexts(
            parser
        )

        self.assertEqual(
            len(rounds),
            2,
        )

        self.assertEqual(
            rounds[0].round_num,
            1,
        )
        self.assertEqual(
            rounds[0].start_tick,
            100,
        )
        self.assertEqual(
            rounds[0].freeze_end_tick,
            200,
        )
        self.assertEqual(
            rounds[0].end_tick,
            900,
        )
        self.assertEqual(
            rounds[0].winner_team,
            3,
        )

        self.assertEqual(
            rounds[1].round_num,
            2,
        )
        self.assertEqual(
            rounds[1].winner_team,
            2,
        )

    def test_uses_last_start_before_round_end(self):
        """
        Если между двумя round_end вдруг оказалось
        несколько round_start, используем последний.

        Это защищает нас от лишнего/служебного start event.
        """

        parser = FakeDemoParser(
            starts=[
                100,
                150,
                1000,
            ],
            freezes=[
                200,
                1100,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1900,
                    "winner": "T",
                },
            ],
        )

        rounds = build_round_contexts(
            parser
        )

        self.assertEqual(
            len(rounds),
            2,
        )

        self.assertEqual(
            rounds[0].start_tick,
            150,
        )

        self.assertEqual(
            rounds[1].start_tick,
            1000,
        )

    def test_missing_freeze_end_falls_back_to_start(self):
        parser = FakeDemoParser(
            starts=[
                100,
            ],
            freezes=[],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
            ],
        )

        rounds = build_round_contexts(
            parser
        )

        self.assertEqual(
            len(rounds),
            1,
        )

        self.assertEqual(
            rounds[0].freeze_end_tick,
            100,
        )

    def test_filters_round_end_after_match_end(self):
        """
        round_end после cs_win_panel_match
        не должен становиться сыгранным раундом.
        """

        parser = FakeDemoParser(
            starts=[
                100,
                1000,
                2000,
            ],
            freezes=[
                200,
                1100,
                2100,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1900,
                    "winner": "T",
                },
                {
                    "tick": 2900,
                    "winner": "CT",
                },
            ],
            panel_ticks=[
                1950,
            ],
        )

        rounds = build_round_contexts(
            parser
        )

        self.assertEqual(
            len(rounds),
            2,
        )

        self.assertEqual(
            rounds[-1].end_tick,
            1900,
        )

    def test_ignores_invalid_round_winner(self):
        parser = FakeDemoParser(
            starts=[
                100,
                1000,
            ],
            freezes=[
                200,
                1100,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "UNKNOWN",
                },
                {
                    "tick": 1900,
                    "winner": "T",
                },
            ],
        )

        rounds = build_round_contexts(
            parser
        )

        self.assertEqual(
            len(rounds),
            1,
        )

        self.assertEqual(
            rounds[0].winner_team,
            2,
        )

    def test_find_round_includes_boundaries(self):
        parser = FakeDemoParser(
            starts=[
                100,
            ],
            freezes=[
                200,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
            ],
        )

        rounds = build_round_contexts(
            parser
        )

        self.assertEqual(
            find_round(
                100,
                rounds,
            ),
            rounds[0],
        )

        self.assertEqual(
            find_round(
                500,
                rounds,
            ),
            rounds[0],
        )

        self.assertEqual(
            find_round(
                900,
                rounds,
            ),
            rounds[0],
        )

        self.assertIsNone(
            find_round(
                901,
                rounds,
            )
        )

    def test_normalize_team_num(self):
        self.assertEqual(
            normalize_team_num("T"),
            2,
        )

        self.assertEqual(
            normalize_team_num("CT"),
            3,
        )

        self.assertEqual(
            normalize_team_num(2),
            2,
        )

        self.assertEqual(
            normalize_team_num(3),
            3,
        )

        self.assertIsNone(
            normalize_team_num(
                "something_weird"
            )
        )


if __name__ == "__main__":
    unittest.main()
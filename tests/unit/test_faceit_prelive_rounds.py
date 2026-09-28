import unittest

import pandas as pd

from src.metrics.round_context import (
    build_round_contexts,
)
from src.parsing.demo_parser import DemoParser


class FakeRawParser:
    def __init__(
        self,
        *,
        faceit_prelive=True,
    ):
        self.faceit_prelive = faceit_prelive

    def parse_events(self, names):
        event = names[0]

        if self.faceit_prelive:
            frames = {
                "round_start": pd.DataFrame([
                    {"tick": 1, "round": 1},
                    {"tick": 3126, "round": 1},
                    {"tick": 3966, "round": 1},
                    {"tick": 4089, "round": 1},
                    {"tick": 11138, "round": 2},
                ]),
                "round_freeze_end": pd.DataFrame([
                    {"tick": 1280},
                    {"tick": 3253},
                    {"tick": 5785},
                    {"tick": 12418},
                ]),
                "round_end": pd.DataFrame([
                    {
                        "tick": 1,
                        "round": 0,
                        "winner": None,
                        "reason": None,
                    },
                    {
                        "tick": 2959,
                        "round": 1,
                        "winner": "T",
                        "reason": "ct_killed",
                    },
                    {
                        "tick": 10690,
                        "round": 2,
                        "winner": "T",
                        "reason": "ct_killed",
                    },
                    {
                        "tick": 17109,
                        "round": 3,
                        "winner": "CT",
                        "reason": "t_killed",
                    },
                ]),
                "begin_new_match": pd.DataFrame([
                    {"tick": 4090},
                ]),
                "cs_win_panel_match": pd.DataFrame([
                    {"tick": 18000},
                ]),
            }

        else:
            frames = {
                "round_start": pd.DataFrame([
                    {"tick": 4089, "round": 1},
                    {"tick": 11138, "round": 2},
                ]),
                "round_freeze_end": pd.DataFrame([
                    {"tick": 5785},
                    {"tick": 12418},
                ]),
                "round_end": pd.DataFrame([
                    {
                        "tick": 10690,
                        "round": 1,
                        "winner": "T",
                        "reason": "ct_killed",
                    },
                    {
                        "tick": 17109,
                        "round": 2,
                        "winner": "CT",
                        "reason": "t_killed",
                    },
                ]),
                "begin_new_match": pd.DataFrame(),
                "cs_win_panel_match": pd.DataFrame([
                    {"tick": 18000},
                ]),
            }

        return frames.get(
            event,
            pd.DataFrame(),
        ).copy()


def make_demo_parser(raw_parser):
    parser = DemoParser.__new__(
        DemoParser
    )
    parser.raw_parser = raw_parser
    return parser


class FaceitPreliveRoundTest(
    unittest.TestCase
):
    def test_demo_parser_excludes_faceit_prelive_rounds(
        self,
    ):
        parser = make_demo_parser(
            FakeRawParser(
                faceit_prelive=True
            )
        )

        rounds = parser._parse_rounds()

        self.assertEqual(
            [
                (
                    round_data.round_num,
                    round_data.end_tick,
                    round_data.winner_side,
                )
                for round_data in rounds
            ],
            [
                (1, 10690, "T"),
                (2, 17109, "CT"),
            ],
        )

    def test_round_context_excludes_faceit_knife_round(
        self,
    ):
        raw_parser = FakeRawParser(
            faceit_prelive=True
        )

        rounds = build_round_contexts(
            raw_parser
        )

        self.assertEqual(
            len(rounds),
            2,
        )

        self.assertEqual(
            (
                rounds[0].round_num,
                rounds[0].start_tick,
                rounds[0].freeze_end_tick,
                rounds[0].end_tick,
                rounds[0].winner_team,
            ),
            (
                1,
                4089,
                5785,
                10690,
                2,
            ),
        )

        self.assertEqual(
            rounds[1].round_num,
            2,
        )

        self.assertEqual(
            rounds[1].end_tick,
            17109,
        )

    def test_normal_demo_without_begin_new_match_still_works(
        self,
    ):
        parser = make_demo_parser(
            FakeRawParser(
                faceit_prelive=False
            )
        )

        rounds = parser._parse_rounds()

        self.assertEqual(
            [
                round_data.round_num
                for round_data in rounds
            ],
            [1, 2],
        )

        self.assertEqual(
            [
                round_data.end_tick
                for round_data in rounds
            ],
            [10690, 17109],
        )


if __name__ == "__main__":
    unittest.main()

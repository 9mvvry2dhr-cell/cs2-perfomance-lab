import unittest

import pandas as pd

from src.metrics.team_context import (
    build_team_state,
    team_relation,
)


class FakeDemoParser:

    def __init__(
        self,
        rows=None,
        fail=False,
    ):
        self.rows = rows or []
        self.fail = fail

    def parse_ticks(
        self,
        fields,
        ticks=None,
    ):
        if self.fail:
            raise RuntimeError(
                "fake parse error"
            )

        wanted_ticks = set(
            ticks or []
        )

        rows = [
            row
            for row in self.rows
            if row["tick"] in wanted_ticks
        ]

        return pd.DataFrame(
            rows
        )


class TestTeamContext(unittest.TestCase):

    def test_builds_team_state(self):
        parser = FakeDemoParser(
            rows=[
                {
                    "tick": 100,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 100,
                    "steamid": "B",
                    "team_num": 3,
                },
            ]
        )

        state = build_team_state(
            parser,
            [100],
        )

        self.assertEqual(
            state[(100, "A")],
            2,
        )

        self.assertEqual(
            state[(100, "B")],
            3,
        )

    def test_supports_side_change_between_ticks(self):
        parser = FakeDemoParser(
            rows=[
                {
                    "tick": 100,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 200,
                    "steamid": "A",
                    "team_num": 3,
                },
            ]
        )

        state = build_team_state(
            parser,
            [
                100,
                200,
            ],
        )

        self.assertEqual(
            state[(100, "A")],
            2,
        )

        self.assertEqual(
            state[(200, "A")],
            3,
        )

    def test_enemy_relation(self):
        state = {
            (100, "A"): 2,
            (100, "B"): 3,
        }

        self.assertEqual(
            team_relation(
                state,
                100,
                "A",
                "B",
            ),
            "enemy",
        )

    def test_teammate_relation(self):
        state = {
            (100, "A"): 2,
            (100, "B"): 2,
        }

        self.assertEqual(
            team_relation(
                state,
                100,
                "A",
                "B",
            ),
            "teammate",
        )

    def test_self_relation(self):
        state = {
            (100, "A"): 2,
        }

        self.assertEqual(
            team_relation(
                state,
                100,
                "A",
                "A",
            ),
            "self",
        )

    def test_unknown_when_team_missing(self):
        state = {
            (100, "A"): 2,
        }

        self.assertEqual(
            team_relation(
                state,
                100,
                "A",
                "B",
            ),
            "unknown",
        )

    def test_parser_failure_returns_empty_state(self):
        parser = FakeDemoParser(
            fail=True
        )

        state = build_team_state(
            parser,
            [100],
        )

        self.assertEqual(
            state,
            {},
        )


if __name__ == "__main__":
    unittest.main()
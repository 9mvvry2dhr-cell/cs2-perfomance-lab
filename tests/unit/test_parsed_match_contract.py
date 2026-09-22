import unittest

from src.parsing.dto import ParsedMatch


class ParsedMatchContractTest(unittest.TestCase):

    def test_player_results_can_be_passed(self):
        match = ParsedMatch(
            match_id="test-match",
            map_name="de_mirage",
            duration_seconds=0,
            rounds_played=20,
            score_ct=13,
            score_t=7,
            winner_side="CT",
            players=[],
            rounds=[],
            player_results={
                "76561198000000001": "win",
            },
        )

        self.assertEqual(
            match.player_results,
            {
                "76561198000000001": "win",
            },
        )

    def test_player_results_defaults_to_empty_dict(self):
        match = ParsedMatch(
            match_id="test-match",
            map_name="de_mirage",
            duration_seconds=0,
            rounds_played=20,
            score_ct=13,
            score_t=7,
            winner_side="CT",
            players=[],
            rounds=[],
        )

        self.assertEqual(
            match.player_results,
            {},
        )


if __name__ == "__main__":
    unittest.main()

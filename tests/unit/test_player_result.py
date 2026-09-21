import unittest

from src.metrics.splits import PlayerRoundSide
from src.parsing.demo_parser import DemoParser
from src.parsing.dto import ParsedPlayer, ParsedRound


def player(steam_id: str) -> ParsedPlayer:
    return ParsedPlayer(
        steam_id=steam_id,
        name=steam_id,
        kills=0,
        deaths=0,
        assists=0,
        damage=0.0,
        headshots=0,
        rounds_played=20,
    )


def rounds(count: int) -> list[ParsedRound]:
    return [
        ParsedRound(
            round_num=index,
            winner_side="CT",
            win_reason="test",
            end_tick=index * 100,
        )
        for index in range(
            1,
            count + 1,
        )
    ]


class PlayerResultTest(unittest.TestCase):

    def _parser(self):
        parser = object.__new__(
            DemoParser
        )

        parser.side_events = []

        return parser


    def test_final_side_maps_to_win_and_loss(self):
        parser = self._parser()

        parser.side_events = [
            PlayerRoundSide(
                round_num=20,
                steam_id="winner",
                side="T",
            ),
            PlayerRoundSide(
                round_num=20,
                steam_id="loser",
                side="CT",
            ),
        ]

        result = parser._derive_player_results(
            players=[
                player("winner"),
                player("loser"),
            ],
            rounds=rounds(20),
            winner_side="T",
            score_ct=7,
            score_t=13,
        )

        self.assertEqual(
            result,
            {
                "winner": "win",
                "loser": "loss",
            },
        )


    def test_missing_final_round_side_fails_closed(self):
        parser = self._parser()

        parser.side_events = [
            PlayerRoundSide(
                round_num=19,
                steam_id="missing",
                side="CT",
            ),
        ]

        result = parser._derive_player_results(
            players=[
                player("missing"),
            ],
            rounds=rounds(20),
            winner_side="T",
            score_ct=7,
            score_t=13,
        )

        self.assertEqual(
            result["missing"],
            "unknown",
        )


    def test_tied_score_is_draw(self):
        parser = self._parser()

        result = parser._derive_player_results(
            players=[
                player("one"),
                player("two"),
            ],
            rounds=rounds(24),
            winner_side="UNKNOWN",
            score_ct=12,
            score_t=12,
        )

        self.assertEqual(
            result,
            {
                "one": "draw",
                "two": "draw",
            },
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from src.domain.growth import (
    evaluate_duel_growth,
)


class DuelGrowthTest(
    unittest.TestCase
):
    def test_real_strong_match_is_not_called_growth_area(
        self,
    ):
        signal = evaluate_duel_growth(
            {
                "contested_duels": 5,
                "contested_wins": 5,
                "contested_losses": 0,
                "contested_win_rate": 100.0,
                "lost_after_first_damage": 0,
                "close_losses": 0,
                "no_return_losses": 4,
                "non_instant_no_return_losses": 2,
                "instant_losses": 2,
            }
        )

        self.assertEqual(
            signal.code,
            "DUEL_REALIZATION",
        )
        self.assertEqual(
            signal.kind,
            "strength",
        )
        self.assertEqual(
            signal.confidence,
            "medium",
        )

    def test_real_bad_match_is_detected_as_growth_area(
        self,
    ):
        signal = evaluate_duel_growth(
            {
                "contested_duels": 9,
                "contested_wins": 1,
                "contested_losses": 8,
                "contested_win_rate": 11.1,
                "lost_after_first_damage": 3,
                "close_losses": 3,
                "no_return_losses": 6,
                "non_instant_no_return_losses": 3,
                "instant_losses": 3,
            }
        )

        self.assertEqual(
            signal.code,
            "DUEL_REALIZATION",
        )
        self.assertEqual(
            signal.kind,
            "growth",
        )
        self.assertEqual(
            signal.confidence,
            "high",
        )

    def test_small_sample_does_not_invent_problem(
        self,
    ):
        signal = evaluate_duel_growth(
            {
                "contested_duels": 2,
                "contested_wins": 0,
                "contested_losses": 2,
                "contested_win_rate": 0.0,
                "lost_after_first_damage": 2,
                "close_losses": 2,
            }
        )

        self.assertEqual(
            signal.kind,
            "insufficient",
        )
        self.assertEqual(
            signal.confidence,
            "none",
        )

    def test_average_duel_match_is_neutral(
        self,
    ):
        signal = evaluate_duel_growth(
            {
                "contested_duels": 6,
                "contested_wins": 3,
                "contested_losses": 3,
                "contested_win_rate": 50.0,
                "lost_after_first_damage": 1,
                "close_losses": 1,
            }
        )

        self.assertEqual(
            signal.kind,
            "neutral",
        )
        self.assertEqual(
            signal.confidence,
            "medium",
        )


if __name__ == "__main__":
    unittest.main()
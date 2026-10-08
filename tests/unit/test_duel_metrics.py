import unittest

import pandas as pd

from src.metrics.duel import (
    calculate_duel_metrics_from_events,
)
from src.metrics.round_context import (
    RoundContext,
)


PLAYER = "player"
ENEMY_1 = "enemy1"
ENEMY_2 = "enemy2"
ENEMY_3 = "enemy3"
TEAMMATE = "teammate"


def make_rounds():
    return [
        RoundContext(
            round_num=1,
            start_tick=0,
            freeze_end_tick=50,
            end_tick=999,
            winner_team=2,
        ),
        RoundContext(
            round_num=2,
            start_tick=1000,
            freeze_end_tick=1050,
            end_tick=1999,
            winner_team=3,
        ),
        RoundContext(
            round_num=3,
            start_tick=2000,
            freeze_end_tick=2050,
            end_tick=2999,
            winner_team=2,
        ),
    ]


def team_map():
    result = {}

    for round_num in (1, 2, 3):
        result[
            (round_num, PLAYER)
        ] = 2

        result[
            (round_num, ENEMY_1)
        ] = 3

        result[
            (round_num, ENEMY_2)
        ] = 3

        result[
            (round_num, ENEMY_3)
        ] = 3

        result[
            (round_num, TEAMMATE)
        ] = 2

    return result


def hurt_row(
    tick,
    attacker,
    victim,
    health,
):
    return {
        "tick": tick,
        "attacker_steamid": attacker,
        "user_steamid": victim,
        "health": health,
    }


def death_row(
    tick,
    attacker,
    victim,
    weapon="ak47",
):
    return {
        "tick": tick,
        "attacker_steamid": attacker,
        "user_steamid": victim,
        "weapon": weapon,
    }


class DuelMetricsTest(
    unittest.TestCase
):
    def calculate(
        self,
        hurt_rows,
        death_rows,
    ):
        result = (
            calculate_duel_metrics_from_events(
                hurt=pd.DataFrame(
                    hurt_rows
                ),
                deaths=pd.DataFrame(
                    death_rows
                ),
                rounds=make_rounds(),
                player_steam_ids=[
                    PLAYER
                ],
                team_by_round_player=(
                    team_map()
                ),
            )
        )

        return result[PLAYER]

    def test_strong_match_preserves_positive_combat_evidence(
        self,
    ):
        actual = self.calculate(
            [
                # R1: clean win.
                hurt_row(
                    100,
                    PLAYER,
                    ENEMY_1,
                    0,
                ),

                # R2: enemy hits first,
                # but player wins contested duel.
                hurt_row(
                    1200,
                    ENEMY_2,
                    PLAYER,
                    70,
                ),
                hurt_row(
                    1210,
                    PLAYER,
                    ENEMY_2,
                    55,
                ),
                hurt_row(
                    1220,
                    PLAYER,
                    ENEMY_2,
                    0,
                ),

                # R3: instant no-return loss.
                hurt_row(
                    2200,
                    ENEMY_3,
                    PLAYER,
                    0,
                ),
            ],
            [
                death_row(
                    100,
                    PLAYER,
                    ENEMY_1,
                ),
                death_row(
                    1220,
                    PLAYER,
                    ENEMY_2,
                ),
                death_row(
                    2200,
                    ENEMY_3,
                    PLAYER,
                    weapon="awp",
                ),
            ],
        )

        self.assertEqual(
            actual["combat_outcomes"],
            3,
        )
        self.assertEqual(
            actual["gun_kills"],
            2,
        )
        self.assertEqual(
            actual["gun_deaths"],
            1,
        )
        self.assertEqual(
            actual["clean_wins"],
            1,
        )
        self.assertEqual(
            actual["contested_duels"],
            1,
        )
        self.assertEqual(
            actual["contested_wins"],
            1,
        )
        self.assertEqual(
            actual["contested_losses"],
            0,
        )
        self.assertEqual(
            actual["contested_win_rate"],
            100.0,
        )
        self.assertEqual(
            actual["no_return_losses"],
            1,
        )
        self.assertEqual(
            actual["instant_losses"],
            1,
        )

    def test_bad_match_preserves_growth_evidence(
        self,
    ):
        actual = self.calculate(
            [
                # R1:
                # player deals first damage,
                # leaves enemy on 25 HP,
                # then loses the duel.
                hurt_row(
                    100,
                    PLAYER,
                    ENEMY_1,
                    25,
                ),
                hurt_row(
                    120,
                    ENEMY_1,
                    PLAYER,
                    50,
                ),
                hurt_row(
                    140,
                    ENEMY_1,
                    PLAYER,
                    0,
                ),

                # R2:
                # player receives multiple hits
                # and never returns damage.
                hurt_row(
                    1200,
                    ENEMY_2,
                    PLAYER,
                    60,
                ),
                hurt_row(
                    1300,
                    ENEMY_2,
                    PLAYER,
                    0,
                ),

                # R3:
                # instant death.
                hurt_row(
                    2200,
                    ENEMY_3,
                    PLAYER,
                    0,
                ),
            ],
            [
                death_row(
                    140,
                    ENEMY_1,
                    PLAYER,
                ),
                death_row(
                    1300,
                    ENEMY_2,
                    PLAYER,
                ),
                death_row(
                    2200,
                    ENEMY_3,
                    PLAYER,
                    weapon="awp",
                ),
            ],
        )

        self.assertEqual(
            actual["combat_outcomes"],
            3,
        )
        self.assertEqual(
            actual["gun_kills"],
            0,
        )
        self.assertEqual(
            actual["gun_deaths"],
            3,
        )

        self.assertEqual(
            actual["contested_duels"],
            1,
        )
        self.assertEqual(
            actual["contested_wins"],
            0,
        )
        self.assertEqual(
            actual["contested_losses"],
            1,
        )
        self.assertEqual(
            actual["contested_win_rate"],
            0.0,
        )

        self.assertEqual(
            actual["lost_after_first_damage"],
            1,
        )
        self.assertEqual(
            actual["first_damage_losses"],
            1,
        )
        self.assertEqual(
            actual["close_losses"],
            1,
        )

        self.assertEqual(
            actual["no_return_losses"],
            2,
        )
        self.assertEqual(
            actual[
                "non_instant_no_return_losses"
            ],
            1,
        )
        self.assertEqual(
            actual["instant_losses"],
            1,
        )

    def test_knife_and_teamkill_are_not_duels(
        self,
    ):
        actual = self.calculate(
            [
                hurt_row(
                    100,
                    PLAYER,
                    ENEMY_1,
                    0,
                ),
                hurt_row(
                    1200,
                    TEAMMATE,
                    PLAYER,
                    0,
                ),
            ],
            [
                death_row(
                    100,
                    PLAYER,
                    ENEMY_1,
                    weapon="knife_t",
                ),
                death_row(
                    1200,
                    TEAMMATE,
                    PLAYER,
                ),
            ],
        )

        self.assertEqual(
            actual["combat_outcomes"],
            0,
        )
        self.assertEqual(
            actual["gun_kills"],
            0,
        )
        self.assertEqual(
            actual["gun_deaths"],
            0,
        )
        self.assertIsNone(
            actual[
                "contested_win_rate"
            ]
        )

    def test_unverified_combat_fails_closed(
        self,
    ):
        actual = self.calculate(
            [],
            [
                death_row(
                    100,
                    PLAYER,
                    ENEMY_1,
                ),
            ],
        )

        self.assertEqual(
            actual["combat_outcomes"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
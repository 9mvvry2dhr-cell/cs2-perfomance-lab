import unittest

import pandas as pd

from src.metrics.utility import calculate_utility_metrics


class FakeDemoParser:

    def __init__(
        self,
        hurts=None,
        blinds=None,
        team_rows=None,
        starts=None,
        freezes=None,
        ends=None,
        panel_ticks=None,
    ):
        self.hurts = hurts or []
        self.blinds = blinds or []
        self.team_rows = team_rows or []

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

        if event_name == "player_hurt":
            return pd.DataFrame(
                self.hurts
            )

        if event_name == "player_blind":
            return pd.DataFrame(
                self.blinds
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


class TestUtilityMetrics(unittest.TestCase):

    def test_enemy_he_damage_counts(self):
        parser = FakeDemoParser(
            hurts=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 35,
                    "health": 65,
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

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["he_damage"],
            35.0,
        )

        self.assertEqual(
            stats["A"]["inferno_damage"],
            0.0,
        )

    def test_team_and_self_damage_are_ignored(self):
        parser = FakeDemoParser(
            hurts=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 30,
                    "health": 70,
                },
                {
                    "tick": 350,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                    "weapon": "hegrenade",
                    "dmg_health": 20,
                    "health": 50,
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
                    "team_num": 2,
                },
            ],
        )

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats,
            {},
        )

    def test_overkill_damage_is_clamped_to_previous_health(self):
        parser = FakeDemoParser(
            hurts=[
                # Обычный weapon hurt сначала уменьшает HP до 20.
                {
                    "tick": 250,
                    "attacker_steamid": "C",
                    "user_steamid": "B",
                    "weapon": "ak47",
                    "dmg_health": 80,
                    "health": 20,
                },
                # HE сообщает 80 raw damage,
                # но реально у жертвы оставалось только 20 HP.
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 80,
                    "health": 0,
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

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["he_damage"],
            20.0,
        )

    def test_enemy_fire_damage_counts(self):
        parser = FakeDemoParser(
            hurts=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "inferno",
                    "dmg_health": 17,
                    "health": 83,
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

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["inferno_damage"],
            17.0,
        )

        self.assertEqual(
            stats["A"]["he_damage"],
            0.0,
        )

    def test_only_enemy_flash_counts(self):
        parser = FakeDemoParser(
            blinds=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "blind_duration": 1.5,
                },
                {
                    "tick": 350,
                    "attacker_steamid": "A",
                    "user_steamid": "C",
                    "blind_duration": 2.0,
                },
                {
                    "tick": 400,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                    "blind_duration": 3.0,
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
                    "tick": 350,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 350,
                    "steamid": "C",
                    "team_num": 2,
                },
            ],
        )

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["enemies_flashed"],
            1,
        )

        self.assertAlmostEqual(
            stats["A"]["flash_duration"],
            1.5,
        )

    def test_events_outside_live_round_are_ignored(self):
        parser = FakeDemoParser(
            hurts=[
                {
                    "tick": 50,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 50,
                    "health": 50,
                },
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 10,
                    "health": 90,
                },
            ],
            blinds=[
                {
                    "tick": 50,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "blind_duration": 5.0,
                },
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "blind_duration": 2.0,
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

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["he_damage"],
            10.0,
        )

        self.assertEqual(
            stats["A"]["enemies_flashed"],
            1,
        )

        self.assertAlmostEqual(
            stats["A"]["flash_duration"],
            2.0,
        )

    def test_side_change_between_rounds_is_supported(self):
        parser = FakeDemoParser(
            hurts=[
                {
                    "tick": 300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 10,
                    "health": 90,
                },
                {
                    "tick": 1300,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                    "weapon": "hegrenade",
                    "dmg_health": 15,
                    "health": 85,
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
                    "tick": 1300,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1300,
                    "steamid": "B",
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
                    "tick": 1900,
                    "winner": "T",
                },
            ],
        )

        stats = calculate_utility_metrics(
            parser
        )

        self.assertEqual(
            stats["A"]["he_damage"],
            25.0,
        )


if __name__ == "__main__":
    unittest.main()
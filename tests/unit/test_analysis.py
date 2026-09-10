import unittest

from src.domain.analysis import (
    build_match_analysis,
    build_player_analysis,
)
from src.parsing.dto import (
    ParsedMatch,
    ParsedPlayer,
)


class TestPlayerAnalysis(unittest.TestCase):

    def _player(self):
        return ParsedPlayer(
            steam_id="123",
            name="test_player",
            kills=24,
            deaths=16,
            assists=5,
            damage=2242.0,
            headshots=10,
            rounds_played=24,
            he_damage=67.0,
            inferno_damage=21.0,
            enemies_flashed=12,
            flash_duration=34.1,
            entry_kills=2,
            entry_deaths=1,
            clutches_won=0,
            trade_kills=3,
            traded_deaths=4,
            kast_rounds=16,
            two_k_rounds=3,
            three_k_rounds=1,
            four_k_rounds=0,
            five_k_rounds=0,
            survived_rounds=8,
        )

    def test_builds_verified_player_analysis(self):
        splits = {
            "CT": {
                "rounds_played": 12,
                "kills": 13,
                "deaths": 8,
                "damage": 1482.0,
                "kast_rounds": 10,
                "survived_rounds": 4,
                "entry_kills": 2,
                "entry_deaths": 0,
            },
            "T": {
                "rounds_played": 12,
                "kills": 11,
                "deaths": 8,
                "damage": 760.0,
                "kast_rounds": 6,
                "survived_rounds": 4,
                "entry_kills": 0,
                "entry_deaths": 1,
            },
        }

        analysis = build_player_analysis(
            self._player(),
            splits,
        )

        self.assertEqual(
            analysis.steam_id,
            "123",
        )

        self.assertEqual(
            analysis.stats.adr,
            93.4,
        )

        self.assertEqual(
            analysis.stats.headshots,
            10,
        )

        self.assertEqual(
            analysis.stats.kd,
            1.5,
        )

        self.assertEqual(
            analysis.stats.headshot_pct,
            41.7,
        )

        self.assertEqual(
            analysis.stats.kast_pct,
            66.7,
        )

        self.assertEqual(
            analysis.sides["CT"].adr,
            123.5,
        )

        self.assertEqual(
            analysis.sides["T"].adr,
            63.3,
        )

        self.assertEqual(
            analysis.sides["CT"].kast_pct,
            83.3,
        )

        self.assertEqual(
            analysis.sides["T"].kast_pct,
            50.0,
        )

        self.assertEqual(
            [
                finding.code
                for finding in analysis.findings
            ],
            [
                "SIDE_PERFORMANCE_GAP",
            ],
        )

        self.assertEqual(
            analysis.findings[0].side,
            "T",
        )

    def test_zero_rounds_are_safe(self):
        player = self._player()
        player.rounds_played = 0
        player.damage = 0.0
        player.kast_rounds = 0
        player.survived_rounds = 0

        analysis = build_player_analysis(
            player,
            {
                "CT": {},
                "T": {},
            },
        )

        self.assertEqual(
            analysis.stats.adr,
            0.0,
        )

        self.assertEqual(
            analysis.stats.kast_pct,
            0.0,
        )

        self.assertEqual(
            analysis.stats.survival_pct,
            0.0,
        )

        self.assertEqual(
            analysis.sides["CT"].adr,
            0.0,
        )

        self.assertEqual(
            analysis.sides["T"].adr,
            0.0,
        )

        self.assertEqual(
            analysis.findings,
            [],
        )




class TestMatchAnalysis(unittest.TestCase):

    def _player(self):
        return ParsedPlayer(
            steam_id="123",
            name="test_player",
            kills=10,
            deaths=8,
            assists=3,
            damage=1000.0,
            headshots=5,
            rounds_played=12,
            kast_rounds=8,
            survived_rounds=4,
        )

    def test_builds_match_analysis(self):
        player = self._player()

        match = ParsedMatch(
            match_id="match_test",
            map_name="de_mirage",
            duration_seconds=1800,
            rounds_played=12,
            score_ct=7,
            score_t=5,
            winner_side="CT",
            players=[player],
            rounds=[],
            is_valid=True,
            validation_error=None,
        )

        splits = {
            "123": {
                "CT": {
                    "rounds_played": 6,
                    "kills": 6,
                    "deaths": 4,
                    "damage": 650.0,
                    "kast_rounds": 5,
                    "survived_rounds": 2,
                    "entry_kills": 1,
                    "entry_deaths": 0,
                },
                "T": {
                    "rounds_played": 6,
                    "kills": 4,
                    "deaths": 4,
                    "damage": 350.0,
                    "kast_rounds": 3,
                    "survived_rounds": 2,
                    "entry_kills": 0,
                    "entry_deaths": 1,
                },
            },
        }

        analysis = build_match_analysis(
            match,
            splits,
        )

        self.assertEqual(
            analysis.match_id,
            "match_test",
        )

        self.assertEqual(
            analysis.map_name,
            "de_mirage",
        )

        self.assertEqual(
            analysis.score_ct,
            7,
        )

        self.assertEqual(
            analysis.score_t,
            5,
        )

        self.assertTrue(
            analysis.is_valid
        )

        self.assertEqual(
            len(analysis.players),
            1,
        )

        self.assertEqual(
            analysis.players[0].steam_id,
            "123",
        )

        self.assertEqual(
            analysis.players[0].stats.adr,
            83.3,
        )

    def test_missing_split_stats_fail_safe(self):
        player = self._player()

        match = ParsedMatch(
            match_id="match_test",
            map_name="de_mirage",
            duration_seconds=1800,
            rounds_played=12,
            score_ct=7,
            score_t=5,
            winner_side="CT",
            players=[player],
            rounds=[],
        )

        analysis = build_match_analysis(
            match,
            {},
        )

        self.assertEqual(
            analysis.players[0]
            .sides["CT"]
            .rounds_played,
            0,
        )

        self.assertEqual(
            analysis.players[0]
            .sides["T"]
            .rounds_played,
            0,
        )

        self.assertEqual(
            analysis.players[0].findings,
            [],
        )


if __name__ == "__main__":
    unittest.main()

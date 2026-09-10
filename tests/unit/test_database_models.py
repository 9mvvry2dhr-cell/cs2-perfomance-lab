import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    Base,
    FindingModel,
    MatchModel,
    MatchPlayerModel,
    PlayerSideStatsModel,
)


class DatabaseModelsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
        )

        Base.metadata.create_all(self.engine)

        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _make_player(self) -> MatchPlayerModel:
        return MatchPlayerModel(
            position=0,
            steam_id="76561198055629469",
            name="kbn_san",
            rounds_played=24,
            kills=24,
            deaths=16,
            assists=1,
            headshots=12,
            damage=2242.0,
            kd=1.5,
            adr=93.4,
            headshot_pct=50.0,
            kast_rounds=16,
            kast_pct=66.7,
            survived_rounds=8,
            survival_pct=33.3,
            entry_kills=2,
            entry_deaths=1,
            he_damage=67.0,
            inferno_damage=21.0,
            enemies_flashed=12,
            flash_duration=34.1,
            clutches_won=1,
            trade_kills=3,
            traded_deaths=2,
            two_k_rounds=8,
            three_k_rounds=1,
            four_k_rounds=0,
            five_k_rounds=0,
        )

    def test_expected_tables_exist(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {
                "matches",
                "match_players",
                "player_side_stats",
                "findings",
            },
        )

    def test_match_graph_can_round_trip_through_database(self):
        player = self._make_player()

        player.sides.extend(
            [
                PlayerSideStatsModel(
                    side="CT",
                    rounds_played=12,
                    kills=13,
                    deaths=8,
                    damage=1482.0,
                    adr=123.5,
                    kast_rounds=10,
                    kast_pct=83.3,
                    survived_rounds=4,
                    survival_pct=33.3,
                    entry_kills=2,
                    entry_deaths=0,
                ),
                PlayerSideStatsModel(
                    side="T",
                    rounds_played=12,
                    kills=11,
                    deaths=8,
                    damage=760.0,
                    adr=63.3,
                    kast_rounds=6,
                    kast_pct=50.0,
                    survived_rounds=4,
                    survival_pct=33.3,
                    entry_kills=0,
                    entry_deaths=1,
                ),
            ]
        )

        player.findings.append(
            FindingModel(
                position=0,
                code="SIDE_PERFORMANCE_GAP",
                category="SIDE_PERFORMANCE",
                side="T",
                evidence={
                    "adr_gap": 60.2,
                    "kast_gap_pct": 33.3,
                },
            )
        )

        match = MatchModel(
            match_id=(
                "match730_003829381261881770506_"
                "1543614415_187"
            ),
            map_name="de_mirage",
            duration_seconds=0,
            rounds_played=24,
            score_ct=13,
            score_t=11,
            winner_side="CT",
            is_valid=True,
            validation_error=None,
            analysis_version="v1",
        )

        match.players.append(player)

        with self.Session() as session:
            session.add(match)
            session.commit()

            loaded = session.get(
                MatchModel,
                match.match_id,
            )

            self.assertIsNotNone(loaded)
            self.assertEqual(
                loaded.map_name,
                "de_mirage",
            )
            self.assertEqual(
                loaded.analysis_version,
                "v1",
            )
            self.assertEqual(
                len(loaded.players),
                1,
            )

            loaded_player = loaded.players[0]

            self.assertEqual(
                loaded_player.steam_id,
                "76561198055629469",
            )
            self.assertEqual(
                loaded_player.adr,
                93.4,
            )

            sides = {
                side.side: side
                for side in loaded_player.sides
            }

            self.assertEqual(
                set(sides),
                {"CT", "T"},
            )
            self.assertEqual(
                sides["CT"].adr,
                123.5,
            )
            self.assertEqual(
                sides["T"].adr,
                63.3,
            )

            self.assertEqual(
                len(loaded_player.findings),
                1,
            )
            self.assertEqual(
                loaded_player.findings[0].code,
                "SIDE_PERFORMANCE_GAP",
            )
            self.assertEqual(
                loaded_player.findings[0].evidence[
                    "adr_gap"
                ],
                60.2,
            )


if __name__ == "__main__":
    unittest.main()

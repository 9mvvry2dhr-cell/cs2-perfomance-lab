import unittest
from dataclasses import replace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.repository import AnalysisRepository
from src.domain.analysis import (
    MatchAnalysis,
    PlayerAnalysis,
    PlayerStats,
    SideStats,
)
from src.domain.insights import Finding


def make_analysis(
    *,
    player_name: str = "kbn_san",
    score_ct: int = 13,
) -> MatchAnalysis:
    stats = PlayerStats(
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

    sides = {
        "CT": SideStats(
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
        "T": SideStats(
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
    }

    findings = [
        Finding(
            code="SIDE_PERFORMANCE_GAP",
            category="side_performance",
            side="T",
            evidence={
                "ct_rounds": 12.0,
                "t_rounds": 12.0,
                "ct_adr": 123.5,
                "t_adr": 63.3,
                "ct_kast_pct": 83.3,
                "t_kast_pct": 50.0,
                "adr_gap": 60.2,
                "kast_gap_pct": 33.3,
            },
        )
    ]

    return MatchAnalysis(
        match_id=(
            "match730_003829381261881770506_"
            "1543614415_187"
        ),
        map_name="de_mirage",
        duration_seconds=0,
        rounds_played=24,
        score_ct=score_ct,
        score_t=11,
        winner_side="CT",
        is_valid=True,
        validation_error=None,
        players=[
            PlayerAnalysis(
                steam_id="76561198055629469",
                name=player_name,
                stats=stats,
                sides=sides,
                findings=findings,
            )
        ],
    )


class AnalysisRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
        )

        Base.metadata.create_all(
            self.engine
        )

        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

        self.session = self.Session()

        self.repository = AnalysisRepository(
            self.session
        )

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(
            self.engine
        )
        self.engine.dispose()

    def test_save_and_get_analysis_round_trip(self):
        expected = make_analysis()

        self.repository.save_analysis(
            expected
        )

        actual = self.repository.get_analysis(
            expected.match_id
        )

        self.assertEqual(
            actual,
            expected,
        )

    def test_get_analysis_returns_none_for_missing_match(self):
        actual = self.repository.get_analysis(
            "missing-match"
        )

        self.assertIsNone(actual)

    def test_saving_same_match_replaces_previous_analysis(self):
        first = make_analysis()

        second = make_analysis(
            player_name="kbn_san_updated",
            score_ct=14,
        )

        self.repository.save_analysis(
            first
        )
        self.repository.save_analysis(
            second
        )

        actual = self.repository.get_analysis(
            second.match_id
        )

        self.assertEqual(
            actual,
            second,
        )


    def test_player_and_finding_order_is_preserved(self):
        base = make_analysis()

        first_player = base.players[0]

        second_finding = Finding(
            code="FREQUENT_OPENING_DEATHS",
            category="entry",
            side="T",
            evidence={
                "rounds_played": 12.0,
                "entry_kills": 0.0,
                "entry_deaths": 3.0,
                "entry_death_gap": 3.0,
                "entry_death_rate_pct": 25.0,
            },
        )

        first_player = replace(
            first_player,
            findings=[
                first_player.findings[0],
                second_finding,
            ],
        )

        second_player = replace(
            first_player,
            steam_id="76561198000000002",
            name="second_player",
            findings=[],
        )

        expected = replace(
            base,
            players=[
                first_player,
                second_player,
            ],
        )

        self.repository.save_analysis(
            expected
        )

        actual = self.repository.get_analysis(
            expected.match_id
        )

        self.assertEqual(
            [
                player.steam_id
                for player in actual.players
            ],
            [
                "76561198055629469",
                "76561198000000002",
            ],
        )

        self.assertEqual(
            [
                finding.code
                for finding
                in actual.players[0].findings
            ],
            [
                "SIDE_PERFORMANCE_GAP",
                "FREQUENT_OPENING_DEATHS",
            ],
        )

        self.assertEqual(
            actual,
            expected,
        )


if __name__ == "__main__":
    unittest.main()

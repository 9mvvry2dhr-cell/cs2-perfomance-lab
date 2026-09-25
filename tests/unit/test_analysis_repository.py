import unittest
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    AnalysisJobModel,
    Base,
    MatchModel,
    MatchPlayerModel,
    UserMatchModel,
    UserModel,
)
from src.database.repository import AnalysisRepository
from src.domain.analysis import (
    MatchAnalysis,
    PlayerAnalysis,
    PlayerStats,
    SideStats,
)
from src.domain.insights import (
    FINDINGS_VERSION,
    Finding,
)


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
            kind="weakness",
            severity="medium",
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


def anonymized_persisted_analysis(
    analysis: MatchAnalysis,
) -> MatchAnalysis:
    players = [
        replace(
            player,
            steam_id=f"anon:{position}",
            name=f"Player {position + 1}",
        )
        for position, player
        in enumerate(analysis.players)
    ]

    player_results = {
        f"anon:{position}": (
            analysis.player_results.get(
                player.steam_id,
                "unknown",
            )
        )
        for position, player
        in enumerate(analysis.players)
    }

    return replace(
        analysis,
        players=players,
        player_results=player_results,
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
            anonymized_persisted_analysis(
                expected
            ),
        )

    def test_player_result_round_trip_is_persisted(self):
        expected = replace(
            make_analysis(),
            player_results={
                "76561198055629469": "win",
            },
        )

        self.repository.save_analysis(
            expected
        )

        actual = self.repository.get_analysis(
            expected.match_id
        )

        self.assertEqual(
            actual.player_results,
            {
                "anon:0": "win",
            },
        )


    def test_save_analysis_does_not_persist_demo_identity(self):
        analysis = replace(
            make_analysis(
                player_name="real-demo-nickname"
            ),
            player_results={
                "76561198055629469": "win",
            },
        )

        self.repository.save_analysis(
            analysis
        )

        stored = self.session.scalar(
            select(
                MatchPlayerModel
            ).where(
                MatchPlayerModel.match_id
                == analysis.match_id
            )
        )

        self.assertIsNotNone(stored)

        self.assertEqual(
            stored.steam_id,
            "anon:0",
        )

        self.assertEqual(
            stored.name,
            "Player 1",
        )

        self.assertEqual(
            stored.result,
            "win",
        )

        self.assertNotEqual(
            stored.steam_id,
            "76561198055629469",
        )

        self.assertNotEqual(
            stored.name,
            "real-demo-nickname",
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
            anonymized_persisted_analysis(
                second
            ),
        )


    def test_get_user_match_position(self):
        analysis = make_analysis()

        owner_steam_id = (
            "76561198055629469"
        )

        self.session.add(
            UserModel(
                steam_id=owner_steam_id,
            )
        )
        self.session.commit()

        self.repository.save_analysis(
            analysis
        )

        self.repository.link_user_match(
            owner_steam_id=owner_steam_id,
            match_id=analysis.match_id,
            player_position=0,
        )

        position = (
            self.repository
            .get_user_match_position(
                owner_steam_id=owner_steam_id,
                match_id=analysis.match_id,
            )
        )

        self.assertEqual(
            position,
            0,
        )

        missing = (
            self.repository
            .get_user_match_position(
                owner_steam_id=owner_steam_id,
                match_id="missing-match",
            )
        )

        self.assertIsNone(
            missing
        )


    def test_reanalysis_preserves_user_match_link(self):
        analysis = make_analysis()

        owner_steam_id = (
            "76561198055629469"
        )

        self.session.add(
            UserModel(
                steam_id=owner_steam_id,
            )
        )
        self.session.commit()

        self.repository.save_analysis(
            analysis
        )

        self.repository.link_user_match(
            owner_steam_id=owner_steam_id,
            match_id=analysis.match_id,
            player_position=0,
        )

        original_link = self.session.get(
            UserMatchModel,
            (
                owner_steam_id,
                analysis.match_id,
            ),
        )

        self.assertIsNotNone(
            original_link
        )

        original_created_at = (
            original_link.created_at
        )

        updated = make_analysis(
            player_name="kbn_san_updated",
            score_ct=14,
        )

        self.repository.save_analysis(
            updated
        )

        preserved_link = self.session.get(
            UserMatchModel,
            (
                owner_steam_id,
                analysis.match_id,
            ),
        )

        self.assertIsNotNone(
            preserved_link
        )

        self.assertEqual(
            preserved_link.player_position,
            0,
        )

        self.assertEqual(
            preserved_link.created_at,
            original_created_at,
        )


    def test_reanalysis_preserves_original_created_at(self):
        first = make_analysis()

        self.repository.save_analysis(
            first
        )

        original_model = self.session.get(
            MatchModel,
            first.match_id,
        )

        original_created_at = datetime(
            2026,
            9,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        )

        original_model.created_at = (
            original_created_at
        )

        self.session.commit()

        updated = replace(
            first,
            player_results={
                "76561198055629469": "win",
            },
        )

        self.repository.save_analysis(
            updated
        )

        refreshed = self.session.get(
            MatchModel,
            first.match_id,
        )

        self.assertEqual(
            refreshed.created_at,
            original_created_at,
        )


    def test_player_and_finding_order_is_preserved(self):
        base = make_analysis()

        first_player = base.players[0]

        second_finding = Finding(
            code="FREQUENT_OPENING_DEATHS",
            category="entry",
            kind="weakness",
            severity="medium",
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
                "anon:0",
                "anon:1",
            ],
        )

        self.assertEqual(
            [
                player.name
                for player in actual.players
            ],
            [
                "Player 1",
                "Player 2",
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
            anonymized_persisted_analysis(
                expected
            ),
        )


    def _save_history_pair(self):
        base = make_analysis()

        owner_steam_id = (
            "76561198055629469"
        )

        self.session.add(
            UserModel(
                steam_id=owner_steam_id,
            )
        )
        self.session.commit()

        first = replace(
            base,
            match_id="match-history-001",
            map_name="de_mirage",
            player_results={
                "76561198055629469": "win",
            },
        )

        duplicate_finding = replace(
            base.players[0].findings[0],
            side="CT",
        )

        second_player = replace(
            base.players[0],
            findings=[
                base.players[0].findings[0],
                duplicate_finding,
            ],
        )

        second = replace(
            base,
            match_id="match-history-002",
            map_name="de_inferno",
            players=[
                second_player
            ],
            player_results={
                "76561198055629469": "loss",
            },
        )

        self.repository.save_analysis(
            first
        )

        self.repository.save_analysis(
            second
        )

        self.repository.link_user_match(
            owner_steam_id=owner_steam_id,
            match_id=first.match_id,
            player_position=0,
        )

        self.repository.link_user_match(
            owner_steam_id=owner_steam_id,
            match_id=second.match_id,
            player_position=0,
        )

        first_model = self.session.get(
            MatchModel,
            first.match_id,
        )

        second_model = self.session.get(
            MatchModel,
            second.match_id,
        )

        first_model.created_at = datetime(
            2026,
            9,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        )

        second_model.created_at = datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        )

        self.session.commit()

        return first, second


    def test_owner_scoped_history_hides_other_users_uploads(self):
        base = make_analysis()

        owned = replace(
            base,
            match_id="owned-history-match",
            map_name="de_mirage",
        )

        foreign = replace(
            base,
            match_id="foreign-history-match",
            map_name="de_ancient",
        )

        self.repository.save_analysis(
            owned
        )

        self.repository.save_analysis(
            foreign
        )

        self.session.add_all(
            [
                UserModel(
                    steam_id="76561198055629469",
                ),
                UserModel(
                    steam_id="76561198000000002",
                ),
            ]
        )
        self.session.commit()

        self.repository.link_user_match(
            owner_steam_id="76561198055629469",
            match_id=owned.match_id,
            player_position=0,
        )

        self.repository.link_user_match(
            owner_steam_id="76561198000000002",
            match_id=foreign.match_id,
            player_position=0,
        )

        history = (
            self.repository
            .get_player_match_history(
                "76561198055629469",
                owner_steam_id=(
                    "76561198055629469"
                ),
                limit=20,
            )
        )

        self.assertEqual(
            [
                item.match_id
                for item in history
            ],
            [
                owned.match_id,
            ],
        )


    def test_player_match_history_is_newest_first(self):
        first, second = self._save_history_pair()

        history = (
            self.repository
            .get_player_match_history(
                "76561198055629469",
                limit=20,
            )
        )

        self.assertEqual(
            [
                item.match_id
                for item in history
            ],
            [
                second.match_id,
                first.match_id,
            ],
        )

        self.assertEqual(
            history[0].map_name,
            "de_inferno",
        )

        self.assertEqual(
            history[0].stats.adr,
            93.4,
        )

        self.assertEqual(
            set(history[0].sides),
            {"CT", "T"},
        )

        self.assertEqual(
            history[0].sides["CT"].adr,
            123.5,
        )

        self.assertEqual(
            history[0].sides["T"].entry_deaths,
            1,
        )

        self.assertEqual(
            history[0].player_result,
            "loss",
        )

        self.assertEqual(
            history[1].player_result,
            "win",
        )


    def test_player_history_keeps_distinct_matches_with_identical_stats(self):
        base = make_analysis()

        owner_steam_id = (
            "76561198055629469"
        )

        self.session.add(
            UserModel(
                steam_id=owner_steam_id,
            )
        )
        self.session.commit()

        first = replace(
            base,
            match_id="identical-stats-001",
        )

        second = replace(
            base,
            match_id="identical-stats-002",
        )

        self.repository.save_analysis(
            first
        )

        self.repository.save_analysis(
            second
        )

        self.repository.link_user_match(
            owner_steam_id=owner_steam_id,
            match_id=first.match_id,
            player_position=0,
        )

        self.repository.link_user_match(
            owner_steam_id=owner_steam_id,
            match_id=second.match_id,
            player_position=0,
        )

        first_model = self.session.get(
            MatchModel,
            first.match_id,
        )

        second_model = self.session.get(
            MatchModel,
            second.match_id,
        )

        first_model.created_at = datetime(
            2026,
            9,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        )

        second_model.created_at = datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        )

        self.session.commit()

        history = (
            self.repository
            .get_player_match_history(
                "76561198055629469",
                limit=20,
            )
        )

        self.assertEqual(
            [
                item.match_id
                for item in history
            ],
            [
                second.match_id,
                first.match_id,
            ],
        )

        summary = (
            self.repository
            .get_player_history_summary(
                "76561198055629469",
                limit=20,
            )
        )

        self.assertIsNotNone(
            summary
        )

        self.assertEqual(
            summary.matches_analyzed,
            2,
        )

        self.assertEqual(
            summary.stats.kills,
            48,
        )


    def test_player_match_history_respects_limit(self):
        _, second = self._save_history_pair()

        history = (
            self.repository
            .get_player_match_history(
                "76561198055629469",
                limit=1,
            )
        )

        self.assertEqual(
            len(history),
            1,
        )

        self.assertEqual(
            history[0].match_id,
            second.match_id,
        )


    def test_player_match_history_returns_empty_for_unknown_player(self):
        history = (
            self.repository
            .get_player_match_history(
                "missing-player",
            )
        )

        self.assertEqual(
            history,
            [],
        )


    def test_player_history_summary_uses_weighted_totals(self):
        self._save_history_pair()

        summary = (
            self.repository
            .get_player_history_summary(
                "76561198055629469",
                limit=10,
            )
        )

        self.assertIsNotNone(
            summary
        )

        self.assertEqual(
            summary.matches_analyzed,
            2,
        )

        self.assertEqual(
            summary.stats.rounds_played,
            48,
        )

        self.assertEqual(
            summary.stats.kills,
            48,
        )

        self.assertEqual(
            summary.stats.deaths,
            32,
        )

        self.assertEqual(
            summary.stats.kd,
            1.5,
        )

        self.assertEqual(
            summary.stats.adr,
            93.4,
        )

        self.assertEqual(
            summary.stats.kast_pct,
            66.7,
        )

        self.assertEqual(
            len(summary.finding_frequency),
            1,
        )

        finding = (
            summary.finding_frequency[0]
        )

        self.assertEqual(
            finding.code,
            "SIDE_PERFORMANCE_GAP",
        )

        # The second match has the same code on two sides.
        # It still counts as one affected match.
        self.assertEqual(
            finding.matches,
            2,
        )

        self.assertEqual(
            finding.match_rate_pct,
            100.0,
        )


    def test_player_history_rejects_invalid_limit(self):
        for limit in (
            0,
            101,
        ):
            with self.subTest(
                limit=limit
            ):
                with self.assertRaises(
                    ValueError
                ):
                    (
                        self.repository
                        .get_player_match_history(
                            "76561198055629469",
                            limit=limit,
                        )
                    )


    def test_refresh_findings_rebuilds_legacy_rows(self):
        analysis = make_analysis()

        self.repository.save_analysis(
            analysis
        )

        match_model = self.session.get(
            MatchModel,
            analysis.match_id,
        )

        original_created_at = (
            match_model.created_at
        )

        self.assertEqual(
            match_model.findings_version,
            FINDINGS_VERSION,
        )

        match_model.findings_version = (
            "legacy"
        )

        self.session.commit()

        updated = (
            self.repository
            .refresh_findings()
        )

        self.assertEqual(
            updated,
            1,
        )

        self.session.expire_all()

        refreshed = self.session.get(
            MatchModel,
            analysis.match_id,
        )

        self.assertEqual(
            refreshed.findings_version,
            FINDINGS_VERSION,
        )

        # SQLite drops timezone metadata when DateTime values
        # are read back. PostgreSQL preserves it. Compare the
        # stored UTC wall-clock value without tzinfo here so this
        # repository test remains backend-neutral.
        self.assertEqual(
            refreshed.created_at.replace(
                tzinfo=None
            ),
            original_created_at.replace(
                tzinfo=None
            ),
        )

        player = refreshed.players[0]

        self.assertEqual(
            [
                finding.code
                for finding
                in player.findings
            ],
            [
                "SIDE_PERFORMANCE_GAP",
                "STRONG_MULTIKILL_IMPACT",
            ],
        )

        # Idempotent: current rows are not rewritten again.
        updated_again = (
            self.repository
            .refresh_findings()
        )

        self.assertEqual(
            updated_again,
            0,
        )


if __name__ == "__main__":
    unittest.main()

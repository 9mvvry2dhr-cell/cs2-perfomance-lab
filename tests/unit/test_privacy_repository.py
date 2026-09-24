import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    AnalysisJobModel,
    AuthSessionModel,
    Base,
    MatchModel,
    UserMatchModel,
    UserModel,
)
from src.database.privacy_repository import (
    ActiveUserAnalysisError,
    DeleteUserDataResult,
    PrivacyRepository,
)


class PrivacyRepositoryTest(
    unittest.TestCase
):
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

        self.repository = PrivacyRepository(
            self.session
        )

        self.now = datetime(
            2026,
            9,
            24,
            12,
            0,
            tzinfo=timezone.utc,
        )

        self.target_steam_id = (
            "76561198055629469"
        )

        self.other_steam_id = (
            "99999999999999999"
        )

        self.session.add_all(
            [
                UserModel(
                    steam_id=(
                        self.target_steam_id
                    ),
                    created_at=self.now,
                    last_login_at=self.now,
                ),
                UserModel(
                    steam_id=(
                        self.other_steam_id
                    ),
                    created_at=self.now,
                    last_login_at=self.now,
                ),
            ]
        )

        self.session.commit()

    def tearDown(self):
        self.session.close()

        Base.metadata.drop_all(
            self.engine
        )

        self.engine.dispose()

    def _add_match(
        self,
        match_id: str,
    ) -> None:
        self.session.add(
            MatchModel(
                match_id=match_id,
                map_name="de_test",
                duration_seconds=1200,
                rounds_played=20,
                score_ct=13,
                score_t=7,
                winner_side="CT",
                is_valid=True,
                validation_error=None,
                analysis_version="v1",
                findings_version="v1",
                created_at=self.now,
            )
        )

        self.session.commit()

    def _add_job(
        self,
        *,
        job_id: str,
        owner_steam_id: str,
        status: str,
        sha: str,
        match_id=None,
    ) -> None:
        finished_at = (
            self.now
            if status in (
                "completed",
                "failed",
            )
            else None
        )

        started_at = (
            self.now
            if status == "processing"
            else None
        )

        self.session.add(
            AnalysisJobModel(
                id=job_id,
                status=status,
                owner_steam_id=(
                    owner_steam_id
                ),
                original_filename=(
                    f"{job_id}.dem"
                ),
                storage_key=(
                    f"{job_id}.dem"
                ),
                file_sha256=sha,
                match_id=match_id,
                created_at=self.now,
                started_at=started_at,
                finished_at=finished_at,
            )
        )

        self.session.commit()

    def _add_session(
        self,
        steam_id: str,
        token_hash: str,
    ) -> None:
        self.session.add(
            AuthSessionModel(
                token_hash=token_hash,
                steam_id=steam_id,
                created_at=self.now,
                expires_at=(
                    self.now
                    + timedelta(days=30)
                ),
                last_seen_at=self.now,
                revoked_at=None,
            )
        )

        self.session.commit()

    def test_export_user_data_contains_only_users_player(
        self,
    ):
        match_id = "f" * 64

        self._add_match(match_id)

        from src.database.models import (
            FindingModel,
            MatchPlayerModel,
            PlayerSideStatsModel,
        )

        target_player = MatchPlayerModel(
            match_id=match_id,
            position=0,
            steam_id="anon:0",
            name="Player 1",
            result="win",
            rounds_played=20,
            kills=20,
            deaths=10,
            assists=5,
            headshots=10,
            damage=2000,
            kd=2.0,
            adr=100.0,
            headshot_pct=50.0,
            kast_rounds=15,
            kast_pct=75.0,
            survived_rounds=10,
            survival_pct=50.0,
            entry_kills=3,
            entry_deaths=1,
            he_damage=50.0,
            inferno_damage=25.0,
            enemies_flashed=8,
            flash_duration=20.0,
            clutches_won=1,
            trade_kills=2,
            traded_deaths=1,
            two_k_rounds=3,
            three_k_rounds=1,
            four_k_rounds=0,
            five_k_rounds=0,
        )

        other_player = MatchPlayerModel(
            match_id=match_id,
            position=1,
            steam_id="anon:1",
            name="Player 2",
            result="loss",
            rounds_played=20,
            kills=1,
            deaths=20,
            assists=0,
            headshots=0,
            damage=100,
            kd=0.05,
            adr=5.0,
            headshot_pct=0.0,
            kast_rounds=2,
            kast_pct=10.0,
            survived_rounds=1,
            survival_pct=5.0,
            entry_kills=0,
            entry_deaths=5,
            he_damage=0.0,
            inferno_damage=0.0,
            enemies_flashed=0,
            flash_duration=0.0,
            clutches_won=0,
            trade_kills=0,
            traded_deaths=5,
            two_k_rounds=0,
            three_k_rounds=0,
            four_k_rounds=0,
            five_k_rounds=0,
        )

        target_player.sides.append(
            PlayerSideStatsModel(
                side="CT",
                rounds_played=10,
                kills=12,
                deaths=4,
                damage=1200,
                adr=120.0,
                kast_rounds=8,
                kast_pct=80.0,
                survived_rounds=6,
                survival_pct=60.0,
                entry_kills=2,
                entry_deaths=0,
            )
        )

        target_player.findings.append(
            FindingModel(
                position=0,
                code="TEST_FINDING",
                category="aim",
                kind="strength",
                severity="low",
                side="CT",
                evidence={
                    "value": 1.0,
                },
            )
        )

        self.session.add_all(
            [
                target_player,
                other_player,
                UserMatchModel(
                    owner_steam_id=(
                        self.target_steam_id
                    ),
                    match_id=match_id,
                    player_position=0,
                    created_at=self.now,
                ),
            ]
        )

        self.session.commit()

        self._add_session(
            self.target_steam_id,
            "secret-token-hash",
        )

        self._add_job(
            job_id="export-job",
            owner_steam_id=(
                self.target_steam_id
            ),
            status="completed",
            sha=match_id,
            match_id=match_id,
        )

        exported = (
            self.repository
            .export_user_data(
                self.target_steam_id
            )
        )

        self.assertEqual(
            exported["steam_id"],
            self.target_steam_id,
        )

        self.assertIsNotNone(
            exported["account"]
        )

        self.assertEqual(
            len(exported["sessions"]),
            1,
        )

        self.assertNotIn(
            "token_hash",
            exported["sessions"][0],
        )

        self.assertEqual(
            len(exported["analysis_jobs"]),
            1,
        )

        self.assertNotIn(
            "storage_key",
            exported["analysis_jobs"][0],
        )

        self.assertEqual(
            len(exported["matches"]),
            1,
        )

        player = (
            exported["matches"][0][
                "player"
            ]
        )

        self.assertEqual(
            player["kills"],
            20,
        )

        self.assertEqual(
            player["result"],
            "win",
        )

        self.assertEqual(
            player["sides"][0]["side"],
            "CT",
        )

        self.assertEqual(
            player["findings"][0]["code"],
            "TEST_FINDING",
        )

        dumped = repr(exported)

        self.assertNotIn(
            "anon:1",
            dumped,
        )

        self.assertNotIn(
            "Player 2",
            dumped,
        )

        self.assertNotIn(
            "secret-token-hash",
            dumped,
        )

    def test_export_unknown_user_is_empty(
        self,
    ):
        exported = (
            self.repository
            .export_user_data(
                "11111111111111111"
            )
        )

        self.assertIsNone(
            exported["account"]
        )

        self.assertEqual(
            exported["sessions"],
            [],
        )

        self.assertEqual(
            exported["analysis_jobs"],
            [],
        )

        self.assertEqual(
            exported["matches"],
            [],
        )

    def test_export_empty_steam_id_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.repository.export_user_data(
                " "
            )


    def test_delete_user_data_removes_owned_data(
        self,
    ):
        only_target = "a" * 64
        shared = "b" * 64

        self._add_match(only_target)
        self._add_match(shared)

        self.session.add_all(
            [
                UserMatchModel(
                    owner_steam_id=(
                        self.target_steam_id
                    ),
                    match_id=only_target,
                    player_position=0,
                    created_at=self.now,
                ),
                UserMatchModel(
                    owner_steam_id=(
                        self.target_steam_id
                    ),
                    match_id=shared,
                    player_position=1,
                    created_at=self.now,
                ),
                UserMatchModel(
                    owner_steam_id=(
                        self.other_steam_id
                    ),
                    match_id=shared,
                    player_position=2,
                    created_at=self.now,
                ),
            ]
        )

        self.session.commit()

        self._add_session(
            self.target_steam_id,
            "target-session",
        )

        self._add_session(
            self.other_steam_id,
            "other-session",
        )

        self._add_job(
            job_id="target-completed",
            owner_steam_id=(
                self.target_steam_id
            ),
            status="completed",
            sha=only_target,
            match_id=only_target,
        )

        self._add_job(
            job_id="target-failed",
            owner_steam_id=(
                self.target_steam_id
            ),
            status="failed",
            sha="c" * 64,
        )

        self._add_job(
            job_id="other-completed",
            owner_steam_id=(
                self.other_steam_id
            ),
            status="completed",
            sha=shared,
            match_id=shared,
        )

        result = (
            self.repository
            .delete_user_data(
                self.target_steam_id
            )
        )

        self.assertEqual(
            result,
            DeleteUserDataResult(
                sessions_deleted=1,
                jobs_deleted=2,
                user_matches_deleted=2,
                user_deleted=1,
                matches_deleted=1,
            ),
        )

        self.assertIsNone(
            self.session.get(
                UserModel,
                self.target_steam_id,
            )
        )

        self.assertIsNotNone(
            self.session.get(
                UserModel,
                self.other_steam_id,
            )
        )

        self.assertEqual(
            self.session.query(
                AuthSessionModel
            ).filter(
                AuthSessionModel.steam_id
                == self.target_steam_id
            ).count(),
            0,
        )

        self.assertEqual(
            self.session.query(
                AnalysisJobModel
            ).filter(
                AnalysisJobModel.owner_steam_id
                == self.target_steam_id
            ).count(),
            0,
        )

        self.assertEqual(
            self.session.query(
                UserMatchModel
            ).filter(
                UserMatchModel.owner_steam_id
                == self.target_steam_id
            ).count(),
            0,
        )

        self.assertIsNone(
            self.session.get(
                MatchModel,
                only_target,
            )
        )

        self.assertIsNotNone(
            self.session.get(
                MatchModel,
                shared,
            )
        )

        other_link = self.session.scalar(
            self.session.query(
                UserMatchModel
            ).filter(
                UserMatchModel.owner_steam_id
                == self.other_steam_id,
                UserMatchModel.match_id
                == shared,
            ).statement
        )

        self.assertIsNotNone(
            other_link
        )

        other_job = self.session.get(
            AnalysisJobModel,
            "other-completed",
        )

        self.assertIsNotNone(
            other_job
        )

        self.assertEqual(
            other_job.match_id,
            shared,
        )

    def test_active_analysis_blocks_deletion(
        self,
    ):
        match_id = "d" * 64

        self._add_match(match_id)

        self.session.add(
            UserMatchModel(
                owner_steam_id=(
                    self.target_steam_id
                ),
                match_id=match_id,
                player_position=0,
                created_at=self.now,
            )
        )

        self.session.commit()

        self._add_session(
            self.target_steam_id,
            "target-session",
        )

        self._add_job(
            job_id="active-job",
            owner_steam_id=(
                self.target_steam_id
            ),
            status="processing",
            sha=match_id,
        )

        with self.assertRaisesRegex(
            ActiveUserAnalysisError,
            "active analysis job",
        ):
            self.repository.delete_user_data(
                self.target_steam_id
            )

        self.assertIsNotNone(
            self.session.get(
                UserModel,
                self.target_steam_id,
            )
        )

        self.assertEqual(
            self.session.query(
                AuthSessionModel
            ).filter(
                AuthSessionModel.steam_id
                == self.target_steam_id
            ).count(),
            1,
        )

        self.assertEqual(
            self.session.query(
                AnalysisJobModel
            ).filter(
                AnalysisJobModel.owner_steam_id
                == self.target_steam_id
            ).count(),
            1,
        )

        self.assertIsNotNone(
            self.session.get(
                MatchModel,
                match_id,
            )
        )

    def test_unknown_user_is_noop(
        self,
    ):
        result = (
            self.repository
            .delete_user_data(
                "11111111111111111"
            )
        )

        self.assertEqual(
            result,
            DeleteUserDataResult(
                sessions_deleted=0,
                jobs_deleted=0,
                user_matches_deleted=0,
                user_deleted=0,
                matches_deleted=0,
            ),
        )

    def test_empty_steam_id_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.repository.delete_user_data(
                "   "
            )


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.maintenance_repository import (
    MaintenanceRepository,
)
from src.database.models import (
    AnalysisJobModel,
    AuthSessionModel,
    Base,
    MatchModel,
    UserMatchModel,
    UserModel,
)


class MaintenanceRepositoryTest(
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

        self.repository = (
            MaintenanceRepository(
                self.session
            )
        )

        self.now = datetime(
            2026,
            9,
            24,
            10,
            0,
            tzinfo=timezone.utc,
        )

        self.user = UserModel(
            steam_id="76561198055629469",
            created_at=self.now,
            last_login_at=self.now,
        )

        self.session.add(self.user)
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
    ) -> MatchModel:
        model = MatchModel(
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

        self.session.add(model)
        self.session.commit()

        return model

    def _add_job(
        self,
        *,
        job_id: str,
        status: str,
        sha: str,
        created_at: datetime,
        finished_at=None,
    ) -> AnalysisJobModel:
        model = AnalysisJobModel(
            id=job_id,
            status=status,
            owner_steam_id=self.user.steam_id,
            original_filename=f"{job_id}.dem",
            storage_key=f"{job_id}.dem",
            file_sha256=sha,
            created_at=created_at,
            finished_at=finished_at,
        )

        self.session.add(model)
        self.session.commit()

        return model

    def test_purge_expired_or_revoked_sessions(
        self,
    ):
        expired = AuthSessionModel(
            token_hash="expired",
            steam_id=self.user.steam_id,
            created_at=(
                self.now - timedelta(days=31)
            ),
            expires_at=(
                self.now - timedelta(seconds=1)
            ),
            last_seen_at=(
                self.now - timedelta(days=1)
            ),
            revoked_at=None,
        )

        revoked = AuthSessionModel(
            token_hash="revoked",
            steam_id=self.user.steam_id,
            created_at=self.now,
            expires_at=(
                self.now + timedelta(days=30)
            ),
            last_seen_at=self.now,
            revoked_at=(
                self.now - timedelta(minutes=1)
            ),
        )

        active = AuthSessionModel(
            token_hash="active",
            steam_id=self.user.steam_id,
            created_at=self.now,
            expires_at=(
                self.now + timedelta(days=30)
            ),
            last_seen_at=self.now,
            revoked_at=None,
        )

        self.session.add_all(
            [
                expired,
                revoked,
                active,
            ]
        )
        self.session.commit()

        count = (
            self.repository
            .purge_expired_or_revoked_sessions(
                now=self.now
            )
        )

        self.assertEqual(count, 2)

        remaining = {
            item.token_hash
            for item in self.session.query(
                AuthSessionModel
            ).all()
        }

        self.assertEqual(
            remaining,
            {"active"},
        )

    def test_purge_only_old_finished_jobs(
        self,
    ):
        old = (
            self.now - timedelta(days=31)
        )

        recent = (
            self.now - timedelta(days=5)
        )

        self._add_job(
            job_id="old-completed",
            status="completed",
            sha="a" * 64,
            created_at=old,
            finished_at=old,
        )

        self._add_job(
            job_id="old-failed",
            status="failed",
            sha="b" * 64,
            created_at=old,
            finished_at=old,
        )

        self._add_job(
            job_id="recent-completed",
            status="completed",
            sha="c" * 64,
            created_at=recent,
            finished_at=recent,
        )

        self._add_job(
            job_id="old-processing",
            status="processing",
            sha="d" * 64,
            created_at=old,
            finished_at=None,
        )

        count = (
            self.repository
            .purge_finished_analysis_jobs(
                finished_before=(
                    self.now
                    - timedelta(days=30)
                )
            )
        )

        self.assertEqual(count, 2)

        remaining = {
            item.id
            for item in self.session.query(
                AnalysisJobModel
            ).all()
        }

        self.assertEqual(
            remaining,
            {
                "recent-completed",
                "old-processing",
            },
        )

    def test_purge_only_old_user_matches(
        self,
    ):
        self._add_match("old-match")
        self._add_match("recent-match")

        old_link = UserMatchModel(
            owner_steam_id=self.user.steam_id,
            match_id="old-match",
            player_position=0,
            created_at=(
                self.now - timedelta(days=91)
            ),
        )

        recent_link = UserMatchModel(
            owner_steam_id=self.user.steam_id,
            match_id="recent-match",
            player_position=0,
            created_at=(
                self.now - timedelta(days=10)
            ),
        )

        self.session.add_all(
            [
                old_link,
                recent_link,
            ]
        )
        self.session.commit()

        count = (
            self.repository
            .purge_user_matches(
                created_before=(
                    self.now
                    - timedelta(days=90)
                )
            )
        )

        self.assertEqual(count, 1)

        remaining = {
            item.match_id
            for item in self.session.query(
                UserMatchModel
            ).all()
        }

        self.assertEqual(
            remaining,
            {"recent-match"},
        )

    def test_purge_orphan_matches_keeps_owned_match(
        self,
    ):
        self._add_match("orphan")
        self._add_match("owned")

        self.session.add(
            UserMatchModel(
                owner_steam_id=(
                    self.user.steam_id
                ),
                match_id="owned",
                player_position=0,
                created_at=self.now,
            )
        )
        self.session.commit()

        count = (
            self.repository
            .purge_orphan_matches()
        )

        self.assertEqual(count, 1)

        remaining = {
            item.match_id
            for item in self.session.query(
                MatchModel
            ).all()
        }

        self.assertEqual(
            remaining,
            {"owned"},
        )

    def test_active_job_protects_orphan_match(
        self,
    ):
        sha = "e" * 64

        self._add_match(sha)

        self._add_job(
            job_id="processing-job",
            status="processing",
            sha=sha,
            created_at=self.now,
            finished_at=None,
        )

        count = (
            self.repository
            .purge_orphan_matches()
        )

        self.assertEqual(count, 0)

        self.assertIsNotNone(
            self.session.get(
                MatchModel,
                sha,
            )
        )


if __name__ == "__main__":
    unittest.main()

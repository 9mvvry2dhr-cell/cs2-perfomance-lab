import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.bug_report_repository import (
    BugReportReferenceError,
    BugReportRepository,
)
from src.database.models import (
    AnalysisJobModel,
    Base,
    MatchModel,
    UserMatchModel,
    UserModel,
)


class BugReportRepositoryTest(
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
            BugReportRepository(
                self.session
            )
        )

        self.now = datetime(
            2026,
            9,
            24,
            13,
            0,
            tzinfo=timezone.utc,
        )

        self.owner = (
            "76561198055629469"
        )

        self.other = (
            "99999999999999999"
        )

        self.session.add_all(
            [
                UserModel(
                    steam_id=self.owner,
                    created_at=self.now,
                    last_login_at=self.now,
                ),
                UserModel(
                    steam_id=self.other,
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
    ):
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
        job_id: str,
        owner_steam_id: str,
    ):
        self.session.add(
            AnalysisJobModel(
                id=job_id,
                status="completed",
                owner_steam_id=(
                    owner_steam_id
                ),
                original_filename="test.dem",
                storage_key="gone.dem",
                file_sha256="a" * 64,
                created_at=self.now,
                finished_at=self.now,
            )
        )

        self.session.commit()

    def test_create_report(
        self,
    ):
        match_id = "m" * 64
        job_id = "job-owned"

        self._add_match(match_id)

        self.session.add(
            UserMatchModel(
                owner_steam_id=self.owner,
                match_id=match_id,
                player_position=0,
                created_at=self.now,
            )
        )

        self.session.commit()

        self._add_job(
            job_id,
            self.owner,
        )

        report = (
            self.repository
            .create_report(
                owner_steam_id=self.owner,
                category="analysis",
                message=(
                    "На экране результата "
                    "неправильный счёт."
                ),
                match_id=match_id,
                job_id=job_id,
            )
        )

        self.assertEqual(
            report.owner_steam_id,
            self.owner,
        )

        self.assertEqual(
            report.category,
            "analysis",
        )

        self.assertEqual(
            report.match_id,
            match_id,
        )

        self.assertEqual(
            report.job_id,
            job_id,
        )

    def test_foreign_match_is_rejected(
        self,
    ):
        match_id = "f" * 64

        self._add_match(match_id)

        self.session.add(
            UserMatchModel(
                owner_steam_id=self.other,
                match_id=match_id,
                player_position=0,
                created_at=self.now,
            )
        )

        self.session.commit()

        with self.assertRaisesRegex(
            BugReportReferenceError,
            "Match is not owned",
        ):
            self.repository.create_report(
                owner_steam_id=self.owner,
                category="statistics",
                message="Неверная статистика ADR.",
                match_id=match_id,
            )

    def test_foreign_job_is_rejected(
        self,
    ):
        self._add_job(
            "foreign-job",
            self.other,
        )

        with self.assertRaisesRegex(
            BugReportReferenceError,
            "Analysis job is not owned",
        ):
            self.repository.create_report(
                owner_steam_id=self.owner,
                category="analysis",
                message="Анализ завис на обработке.",
                job_id="foreign-job",
            )

    def test_invalid_category_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported",
        ):
            self.repository.create_report(
                owner_steam_id=self.owner,
                category="banana",
                message="Что-то сломалось.",
            )

    def test_short_message_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "too short",
        ):
            self.repository.create_report(
                owner_steam_id=self.owner,
                category="ui",
                message="bug",
            )


if __name__ == "__main__":
    unittest.main()

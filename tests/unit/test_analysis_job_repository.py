import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.job_repository import (
    AnalysisJobNotFoundError,
    AnalysisJobRepository,
    InvalidAnalysisJobTransitionError,
)
from src.database.models import (
    Base,
    MatchModel,
)


class AnalysisJobRepositoryTest(
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
            AnalysisJobRepository(
                self.session
            )
        )

    def tearDown(self):
        self.session.close()

        Base.metadata.drop_all(
            self.engine
        )

        self.engine.dispose()

    def _create_job(self):
        return self.repository.create_job(
            original_filename="match.dem",
            storage_key=(
                "demos/test-match.dem"
            ),
            file_sha256="a" * 64,
        )

    def _create_match(
        self,
        match_id: str,
    ):
        self.session.add(
            MatchModel(
                match_id=match_id,
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
        )

        self.session.commit()

    def test_create_and_get_job(self):
        created = self._create_job()

        loaded = self.repository.get_job(
            created.id
        )

        self.assertEqual(
            loaded,
            created,
        )

        self.assertEqual(
            loaded.status,
            "queued",
        )

        self.assertIsNotNone(
            loaded.created_at
        )

        self.assertIsNone(
            loaded.started_at
        )

        self.assertIsNone(
            loaded.finished_at
        )

    def test_get_job_returns_none_when_missing(
        self,
    ):
        loaded = self.repository.get_job(
            "missing-job"
        )

        self.assertIsNone(
            loaded
        )

    def test_mark_processing(self):
        created = self._create_job()

        processing = (
            self.repository.mark_processing(
                created.id
            )
        )

        self.assertEqual(
            processing.status,
            "processing",
        )

        self.assertIsNotNone(
            processing.started_at
        )

        self.assertIsNone(
            processing.finished_at
        )

    def test_mark_completed(self):
        created = self._create_job()

        self.repository.mark_processing(
            created.id
        )

        self._create_match(
            "match-001"
        )

        completed = (
            self.repository.mark_completed(
                created.id,
                match_id="match-001",
            )
        )

        self.assertEqual(
            completed.status,
            "completed",
        )

        self.assertEqual(
            completed.match_id,
            "match-001",
        )

        self.assertIsNone(
            completed.error
        )

        self.assertIsNotNone(
            completed.finished_at
        )

    def test_mark_failed(self):
        created = self._create_job()

        self.repository.mark_processing(
            created.id
        )

        failed = (
            self.repository.mark_failed(
                created.id,
                error="Parser failed",
            )
        )

        self.assertEqual(
            failed.status,
            "failed",
        )

        self.assertEqual(
            failed.error,
            "Parser failed",
        )

        self.assertIsNone(
            failed.match_id
        )

        self.assertIsNotNone(
            failed.finished_at
        )

    def test_invalid_transition_is_rejected(
        self,
    ):
        created = self._create_job()

        with self.assertRaises(
            InvalidAnalysisJobTransitionError
        ):
            self.repository.mark_completed(
                created.id,
                match_id="match-001",
            )

        loaded = self.repository.get_job(
            created.id
        )

        self.assertEqual(
            loaded.status,
            "queued",
        )

    def test_missing_job_transition_is_rejected(
        self,
    ):
        with self.assertRaises(
            AnalysisJobNotFoundError
        ):
            self.repository.mark_processing(
                "missing-job"
            )


if __name__ == "__main__":
    unittest.main()

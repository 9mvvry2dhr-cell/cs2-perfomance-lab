import unittest
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    LocalDemoStorage,
)
from src.workers.analysis_worker import (
    AnalysisWorker,
    DemoOwnerNotFoundError,
)
from tests.unit.test_analysis_repository import (
    make_analysis,
)


NOW = datetime(
    2026,
    9,
    11,
    8,
    0,
    tzinfo=timezone.utc,
)

TEST_STEAM_ID = "76561198055629469"
OTHER_STEAM_ID = "76561198000000000"


class StubJobRepository:
    def __init__(
        self,
        job: AnalysisJob,
    ):
        self.job = job
        self.failed_error = None
        self.mark_processing_calls = 0
        self.claimed = False

    def claim_next_job(
        self,
    ) -> AnalysisJob | None:
        if (
            self.claimed
            or self.job.status
            != "queued"
        ):
            return None

        self.claimed = True

        self.job = replace(
            self.job,
            status="processing",
            started_at=NOW,
        )

        return self.job

    def mark_processing(
        self,
        job_id: str,
    ) -> AnalysisJob:
        self.mark_processing_calls += 1

        self.job = replace(
            self.job,
            status="processing",
            started_at=NOW,
        )

        return self.job

    def mark_completed(
        self,
        job_id: str,
        *,
        match_id: str,
    ) -> AnalysisJob:
        self.job = replace(
            self.job,
            status="completed",
            match_id=match_id,
            finished_at=NOW,
        )

        return self.job

    def mark_failed(
        self,
        job_id: str,
        *,
        error: str,
    ) -> AnalysisJob:
        self.failed_error = error

        self.job = replace(
            self.job,
            status="failed",
            error=error,
            finished_at=NOW,
        )

        return self.job


class StubAnalysisRepository:
    def __init__(self):
        self.saved = None
        self.user_match_links = []

    def save_analysis(
        self,
        analysis,
    ):
        self.saved = analysis

    def link_user_match(
        self,
        *,
        owner_steam_id,
        match_id,
        player_position,
    ):
        self.user_match_links.append(
            (
                owner_steam_id,
                match_id,
                player_position,
            )
        )


class AnalysisWorkerTest(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = (
            TemporaryDirectory()
        )

        self.storage = LocalDemoStorage(
            Path(self.temp_dir.name)
        )

        self.stored = (
            self.storage.store(
                original_filename=(
                    "match.dem"
                ),
                source=BytesIO(
                    b"demo-content"
                ),
            )
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_job(self):
        return AnalysisJob(
            id="job-001",
            status="queued",
            original_filename="match.dem",
            storage_key=(
                self.stored.storage_key
            ),
            file_sha256=(
                self.stored.file_sha256
            ),
            match_id=None,
            error=None,
            created_at=NOW,
            started_at=None,
            finished_at=None,
            owner_steam_id=TEST_STEAM_ID,
        )

    def test_process_completes_job_saves_analysis_and_deletes_demo(
        self,
    ):
        expected_analysis = (
            make_analysis()
        )

        jobs = StubJobRepository(
            self._make_job()
        )

        analyses = (
            StubAnalysisRepository()
        )

        demo_path = (
            self.storage.path_for(
                self.stored.storage_key
            )
        )

        self.assertTrue(
            demo_path.is_file()
        )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
            analyzer=lambda _: (
                expected_analysis
            ),
        )

        result = worker.process(
            "job-001"
        )

        self.assertEqual(
            result.status,
            "completed",
        )

        expected_saved = replace(
            expected_analysis,
            match_id=self.stored.file_sha256,
        )

        self.assertEqual(
            result.match_id,
            self.stored.file_sha256,
        )

        self.assertEqual(
            analyses.saved,
            expected_saved,
        )

        self.assertEqual(
            analyses.user_match_links,
            [
                (
                    TEST_STEAM_ID,
                    self.stored.file_sha256,
                    0,
                )
            ],
        )

        self.assertFalse(
            demo_path.exists()
        )

    def test_process_next_claims_completes_and_deletes_demo(
        self,
    ):
        expected_analysis = (
            make_analysis()
        )

        jobs = StubJobRepository(
            self._make_job()
        )

        analyses = (
            StubAnalysisRepository()
        )

        demo_path = (
            self.storage.path_for(
                self.stored.storage_key
            )
        )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
            analyzer=lambda _: (
                expected_analysis
            ),
        )

        result = worker.process_next()

        self.assertIsNotNone(
            result
        )

        self.assertEqual(
            result.status,
            "completed",
        )

        self.assertEqual(
            result.match_id,
            self.stored.file_sha256,
        )

        self.assertEqual(
            jobs.mark_processing_calls,
            0,
        )

        self.assertEqual(
            analyses.saved,
            replace(
                expected_analysis,
                match_id=self.stored.file_sha256,
            ),
        )

        self.assertFalse(
            demo_path.exists()
        )

    def test_process_next_returns_none_when_queue_empty(
        self,
    ):
        jobs = StubJobRepository(
            self._make_job()
        )

        jobs.claimed = True

        analyses = (
            StubAnalysisRepository()
        )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
        )

        result = worker.process_next()

        self.assertIsNone(
            result
        )

        self.assertEqual(
            jobs.mark_processing_calls,
            0,
        )

        self.assertIsNone(
            analyses.saved
        )

    def test_process_rejects_demo_without_owner(
        self,
    ):
        expected_analysis = make_analysis()

        foreign_job = replace(
            self._make_job(),
            owner_steam_id=OTHER_STEAM_ID,
        )

        jobs = StubJobRepository(
            foreign_job
        )

        analyses = StubAnalysisRepository()

        demo_path = self.storage.path_for(
            self.stored.storage_key
        )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
            analyzer=lambda _: expected_analysis,
        )

        with self.assertRaises(
            DemoOwnerNotFoundError
        ):
            worker.process(
                foreign_job.id
            )

        self.assertEqual(
            jobs.job.status,
            "failed",
        )

        self.assertEqual(
            jobs.failed_error,
            (
                "Authenticated Steam account "
                "was not found in demo"
            ),
        )

        self.assertIsNone(
            analyses.saved
        )

        self.assertFalse(
            demo_path.exists()
        )

    def test_process_marks_job_failed_and_deletes_demo_when_analysis_fails(
        self,
    ):
        jobs = StubJobRepository(
            self._make_job()
        )

        analyses = (
            StubAnalysisRepository()
        )

        demo_path = (
            self.storage.path_for(
                self.stored.storage_key
            )
        )

        def fail(_):
            raise RuntimeError(
                "parser exploded"
            )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
            analyzer=fail,
        )

        with self.assertRaises(
            RuntimeError
        ):
            worker.process(
                "job-001"
            )

        self.assertEqual(
            jobs.job.status,
            "failed",
        )

        self.assertEqual(
            jobs.failed_error,
            "Analysis failed",
        )

        self.assertIsNone(
            analyses.saved
        )

        self.assertFalse(
            demo_path.exists()
        )

    def test_process_stays_failed_when_failed_demo_cleanup_fails(
        self,
    ):
        jobs = StubJobRepository(
            self._make_job()
        )

        analyses = (
            StubAnalysisRepository()
        )

        demo_path = (
            self.storage.path_for(
                self.stored.storage_key
            )
        )

        def fail(_):
            raise RuntimeError(
                "parser exploded"
            )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
            analyzer=fail,
        )

        with patch.object(
            self.storage,
            "delete",
            side_effect=OSError(
                "cleanup failed"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "parser exploded",
            ):
                worker.process(
                    "job-001"
                )

        self.assertEqual(
            jobs.job.status,
            "failed",
        )

        self.assertEqual(
            jobs.failed_error,
            "Analysis failed",
        )

        self.assertIsNone(
            analyses.saved
        )

        self.assertTrue(
            demo_path.is_file()
        )

    def test_process_stays_completed_when_demo_cleanup_fails(
        self,
    ):
        expected_analysis = (
            make_analysis()
        )

        jobs = StubJobRepository(
            self._make_job()
        )

        analyses = (
            StubAnalysisRepository()
        )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
            analyzer=lambda _: (
                expected_analysis
            ),
        )

        with patch.object(
            self.storage,
            "delete",
            side_effect=OSError(
                "cleanup failed"
            ),
        ):
            result = worker.process(
                "job-001"
            )

        self.assertEqual(
            result.status,
            "completed",
        )

        self.assertEqual(
            jobs.job.status,
            "completed",
        )

        self.assertIsNone(
            jobs.failed_error
        )

        self.assertIsNotNone(
            analyses.saved
        )

        self.assertTrue(
            self.storage.path_for(
                self.stored.storage_key
            ).is_file()
        )

    def test_process_marks_job_failed_when_demo_is_missing(
        self,
    ):
        job = self._make_job()

        self.storage.delete(
            job.storage_key
        )

        jobs = StubJobRepository(
            job
        )

        analyses = (
            StubAnalysisRepository()
        )

        worker = AnalysisWorker(
            storage=self.storage,
            job_repository=jobs,
            analysis_repository=analyses,
        )

        with self.assertRaises(
            FileNotFoundError
        ):
            worker.process(
                job.id
            )

        self.assertEqual(
            jobs.job.status,
            "failed",
        )

        self.assertEqual(
            jobs.failed_error,
            "Analysis failed",
        )


if __name__ == "__main__":
    unittest.main()

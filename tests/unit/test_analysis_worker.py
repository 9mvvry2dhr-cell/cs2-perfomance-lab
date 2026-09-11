import unittest
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    LocalDemoStorage,
)
from src.workers.analysis_worker import (
    AnalysisWorker,
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


class StubJobRepository:
    def __init__(
        self,
        job: AnalysisJob,
    ):
        self.job = job
        self.failed_error = None

    def mark_processing(
        self,
        job_id: str,
    ) -> AnalysisJob:
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

    def save_analysis(
        self,
        analysis,
    ):
        self.saved = analysis


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
        )

    def test_process_completes_job_and_saves_analysis(
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

        result = worker.process(
            "job-001"
        )

        self.assertEqual(
            result.status,
            "completed",
        )

        expected_saved = replace(
            expected_analysis,
            match_id="match",
        )

        self.assertEqual(
            result.match_id,
            "match",
        )

        self.assertEqual(
            analyses.saved,
            expected_saved,
        )

    def test_process_marks_job_failed_when_analysis_fails(
        self,
    ):
        jobs = StubJobRepository(
            self._make_job()
        )

        analyses = (
            StubAnalysisRepository()
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

import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import (
    get_analysis_job_repository,
)
from src.api.schemas import AnalysisJobResponse
from src.domain.jobs import AnalysisJob


class StubAnalysisJobRepository:
    def __init__(self, job=None):
        self.job = job

    def get_job(
        self,
        job_id: str,
    ):
        if (
            self.job is not None
            and self.job.id == job_id
        ):
            return self.job

        return None


def make_job() -> AnalysisJob:
    now = datetime(
        2026,
        9,
        11,
        7,
        30,
        tzinfo=timezone.utc,
    )

    return AnalysisJob(
        id="job-001",
        status="processing",
        original_filename="match.dem",
        storage_key="demos/job-001.dem",
        file_sha256="a" * 64,
        match_id=None,
        error=None,
        created_at=now,
        started_at=now,
        finished_at=None,
    )


class AnalysisJobApiTest(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_get_job_returns_job(self):
        expected = make_job()

        app.dependency_overrides[
            get_analysis_job_repository
        ] = lambda: StubAnalysisJobRepository(
            expected
        )

        client = TestClient(app)

        response = client.get(
            f"/analysis-jobs/{expected.id}"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected_json = (
            AnalysisJobResponse
            .model_validate(expected)
            .model_dump(mode="json")
        )

        self.assertEqual(
            response.json(),
            expected_json,
        )

        self.assertNotIn(
            "storage_key",
            response.json(),
        )

        self.assertNotIn(
            "file_sha256",
            response.json(),
        )

    def test_get_job_returns_404_when_missing(
        self,
    ):
        app.dependency_overrides[
            get_analysis_job_repository
        ] = lambda: StubAnalysisJobRepository()

        client = TestClient(app)

        response = client.get(
            "/analysis-jobs/missing-job"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": "Analysis job not found",
            },
        )


if __name__ == "__main__":
    unittest.main()

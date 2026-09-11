import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import (
    get_demo_ingestion_service,
)
from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    DemoTooLargeError,
    InvalidDemoFileError,
)


def make_queued_job() -> AnalysisJob:
    now = datetime(
        2026,
        9,
        11,
        8,
        0,
        tzinfo=timezone.utc,
    )

    return AnalysisJob(
        id="upload-job-001",
        status="queued",
        original_filename="match.dem",
        storage_key="internal.dem",
        file_sha256="a" * 64,
        match_id=None,
        error=None,
        created_at=now,
        started_at=None,
        finished_at=None,
    )


class StubIngestionService:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.filename = None
        self.payload = None

    def ingest(
        self,
        *,
        original_filename,
        source,
    ):
        self.filename = original_filename
        self.payload = source.read()

        if self.error is not None:
            raise self.error

        return self.result


class AnalysisJobUploadApiTest(
    unittest.TestCase
):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_upload_demo_creates_queued_job(
        self,
    ):
        expected = make_queued_job()

        service = StubIngestionService(
            result=expected
        )

        app.dependency_overrides[
            get_demo_ingestion_service
        ] = lambda: service

        client = TestClient(app)

        response = client.post(
            "/analysis-jobs",
            files={
                "file": (
                    "match.dem",
                    b"demo-content",
                    "application/octet-stream",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            202,
        )

        self.assertEqual(
            service.filename,
            "match.dem",
        )

        self.assertEqual(
            service.payload,
            b"demo-content",
        )

        body = response.json()

        self.assertEqual(
            body["id"],
            "upload-job-001",
        )

        self.assertEqual(
            body["status"],
            "queued",
        )

        self.assertNotIn(
            "storage_key",
            body,
        )

        self.assertNotIn(
            "file_sha256",
            body,
        )

    def test_upload_rejects_non_demo_file(
        self,
    ):
        service = StubIngestionService(
            error=InvalidDemoFileError(
                "Only .dem files are supported"
            )
        )

        app.dependency_overrides[
            get_demo_ingestion_service
        ] = lambda: service

        client = TestClient(app)

        response = client.post(
            "/analysis-jobs",
            files={
                "file": (
                    "match.zip",
                    b"content",
                    "application/octet-stream",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Only .dem files are supported"
                )
            },
        )

    def test_upload_rejects_too_large_demo(
        self,
    ):
        service = StubIngestionService(
            error=DemoTooLargeError(
                "Demo file is too large"
            )
        )

        app.dependency_overrides[
            get_demo_ingestion_service
        ] = lambda: service

        client = TestClient(app)

        response = client.post(
            "/analysis-jobs",
            files={
                "file": (
                    "match.dem",
                    b"content",
                    "application/octet-stream",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            413,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Demo file is too large"
                )
            },
        )


if __name__ == "__main__":
    unittest.main()

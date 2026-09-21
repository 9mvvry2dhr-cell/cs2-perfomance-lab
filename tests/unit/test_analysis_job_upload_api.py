import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import (
    get_current_user,
    get_demo_ingestion_service,
)
from src.domain.identity import CurrentUser
from src.domain.jobs import AnalysisJob
from src.ingestion.service import (
    AnalysisAlreadyActiveError,
    AnalysisQueueFullError,
    DuplicateDemoError,
)
from src.ingestion.storage import (
    DemoStorageFullError,
    DemoTooLargeError,
    InvalidDemoFileError,
)


TEST_STEAM_ID = "76561198055629469"


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
        self.owner_steam_id = None

    def ingest(
        self,
        *,
        owner_steam_id,
        original_filename,
        source,
    ):
        self.owner_steam_id = owner_steam_id
        self.filename = original_filename
        self.payload = source.read()

        if self.error is not None:
            raise self.error

        return self.result


class AnalysisJobUploadApiTest(
    unittest.TestCase
):
    def setUp(self):
        app.dependency_overrides[
            get_current_user
        ] = lambda: CurrentUser(
            steam_id=TEST_STEAM_ID
        )

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
            service.owner_steam_id,
            TEST_STEAM_ID,
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

    def test_upload_rejects_when_analysis_queue_is_full(
        self,
    ):
        service = StubIngestionService(
            error=AnalysisQueueFullError(
                "Analysis queue is full"
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
            429,
        )

        self.assertEqual(
            response.headers.get(
                "retry-after"
            ),
            "30",
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Analysis queue is full"
                )
            },
        )

    def test_upload_rejects_when_user_already_has_active_analysis(
        self,
    ):
        service = StubIngestionService(
            error=AnalysisAlreadyActiveError(
                "An analysis is already active "
                "for this Steam account"
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
                    "second.dem",
                    b"content",
                    "application/octet-stream",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            429,
        )

        self.assertEqual(
            response.headers.get(
                "retry-after"
            ),
            "30",
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "An analysis is already active "
                    "for this Steam account"
                )
            },
        )

    def test_upload_rejects_already_analyzed_demo(
        self,
    ):
        service = StubIngestionService(
            error=DuplicateDemoError(
                "This demo has already been analyzed"
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
                    "duplicate.dem",
                    b"content",
                    "application/octet-stream",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            409,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "This demo has already been analyzed"
                )
            },
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

    def test_upload_rejects_when_demo_storage_is_full(
        self,
    ):
        service = StubIngestionService(
            error=DemoStorageFullError(
                "Demo storage is full"
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
            507,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Demo storage is full"
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

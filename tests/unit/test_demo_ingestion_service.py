import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ingestion.service import (
    AnalysisQueueFullError,
    DemoIngestionService,
)
from src.ingestion.storage import (
    LocalDemoStorage,
)


class StubJobRepository:
    def __init__(
        self,
        *,
        result=None,
        error=None,
        active_jobs=0,
    ):
        self.result = result
        self.error = error
        self.active_jobs = active_jobs
        self.calls = []

    def count_active_jobs(
        self,
    ):
        return self.active_jobs

    def create_job(
        self,
        *,
        owner_steam_id,
        original_filename,
        storage_key,
        file_sha256,
    ):
        self.calls.append(
            {
                "owner_steam_id": (
                    owner_steam_id
                ),
                "original_filename": (
                    original_filename
                ),
                "storage_key": storage_key,
                "file_sha256": file_sha256,
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


class DemoIngestionServiceTest(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = (
            TemporaryDirectory()
        )

        self.root = Path(
            self.temp_dir.name
        )

        self.storage = LocalDemoStorage(
            self.root
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ingest_stores_demo_and_creates_job(
        self,
    ):
        expected_job = object()

        repository = StubJobRepository(
            result=expected_job
        )

        service = DemoIngestionService(
            storage=self.storage,
            job_repository=repository,
        )

        result = service.ingest(
            owner_steam_id="76561198055629469",
            original_filename="match.dem",
            source=BytesIO(
                b"demo-content"
            ),
        )

        self.assertIs(
            result,
            expected_job,
        )

        self.assertEqual(
            len(repository.calls),
            1,
        )

        call = repository.calls[0]

        self.assertEqual(
            call["owner_steam_id"],
            "76561198055629469",
        )

        self.assertEqual(
            call["original_filename"],
            "match.dem",
        )

        self.assertEqual(
            len(call["file_sha256"]),
            64,
        )

        self.assertTrue(
            (
                self.root
                / call["storage_key"]
            ).exists()
        )

    def test_ingest_rejects_when_active_job_limit_is_reached(
        self,
    ):
        repository = StubJobRepository(
            active_jobs=4
        )

        service = DemoIngestionService(
            storage=self.storage,
            job_repository=repository,
            max_active_jobs=4,
        )

        with self.assertRaises(
            AnalysisQueueFullError
        ):
            service.ingest(
                owner_steam_id="76561198055629469",
                original_filename="match.dem",
                source=BytesIO(
                    b"demo-content"
                ),
            )

        self.assertEqual(
            repository.calls,
            [],
        )

        self.assertEqual(
            list(self.root.iterdir()),
            [],
        )

    def test_ingest_deletes_demo_when_job_creation_fails(
        self,
    ):
        repository = StubJobRepository(
            error=RuntimeError(
                "database failed"
            )
        )

        service = DemoIngestionService(
            storage=self.storage,
            job_repository=repository,
        )

        with self.assertRaises(
            RuntimeError
        ):
            service.ingest(
                owner_steam_id="76561198055629469",
                original_filename="match.dem",
                source=BytesIO(
                    b"demo-content"
                ),
            )

        self.assertEqual(
            list(
                self.root.iterdir()
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()

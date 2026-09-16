import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ingestion.service import (
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
    ):
        self.result = result
        self.error = error
        self.calls = []

    def create_job(
        self,
        *,
        original_filename,
        storage_key,
        file_sha256,
    ):
        self.calls.append(
            {
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

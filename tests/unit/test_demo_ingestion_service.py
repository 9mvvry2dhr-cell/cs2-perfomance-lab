import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.database.job_repository import (
    ActiveAnalysisJobConflictError,
)
from src.ingestion.service import (
    AnalysisAlreadyActiveError,
    AnalysisQueueFullError,
    DemoIngestionService,
    DuplicateDemoError,
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
        owner_active_jobs=0,
        completed_duplicate=False,
        completed_job=None,
    ):
        self.result = result
        self.error = error
        self.active_jobs = active_jobs
        self.owner_active_jobs = (
            owner_active_jobs
        )
        self.completed_duplicate = (
            completed_duplicate
        )
        self.completed_job = completed_job
        self.calls = []

    def count_active_jobs(
        self,
    ):
        return self.active_jobs

    def count_active_jobs_for_owner(
        self,
        owner_steam_id,
    ):
        return self.owner_active_jobs

    def get_completed_file_for_owner(
        self,
        owner_steam_id,
        file_sha256,
    ):
        if self.completed_job is not None:
            return self.completed_job

        if self.completed_duplicate:
            return object()

        return None

    def has_completed_file_for_owner(
        self,
        owner_steam_id,
        file_sha256,
    ):
        return (
            self.get_completed_file_for_owner(
                owner_steam_id,
                file_sha256,
            )
            is not None
        )

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


class StubAnalysisRepository:
    def __init__(
        self,
        *,
        user_match_position=None,
    ):
        self.user_match_position = (
            user_match_position
        )
        self.calls = []

    def get_user_match_position(
        self,
        *,
        owner_steam_id,
        match_id,
    ):
        self.calls.append(
            {
                "owner_steam_id": owner_steam_id,
                "match_id": match_id,
            }
        )

        return self.user_match_position


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
            analysis_repository=(
                StubAnalysisRepository()
            ),
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

    def test_ingest_rejects_second_active_job_for_same_owner(
        self,
    ):
        repository = StubJobRepository(
            active_jobs=1,
            owner_active_jobs=1,
        )

        service = DemoIngestionService(
            storage=self.storage,
            job_repository=repository,
            analysis_repository=(
                StubAnalysisRepository()
            ),
            max_active_jobs=4,
        )

        with self.assertRaises(
            AnalysisAlreadyActiveError
        ):
            service.ingest(
                owner_steam_id="76561198055629469",
                original_filename="second.dem",
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

    def test_ingest_translates_database_active_job_race(
        self,
    ):
        repository = StubJobRepository(
            error=ActiveAnalysisJobConflictError(
                "Owner already has an "
                "active analysis job"
            )
        )

        service = DemoIngestionService(
            storage=self.storage,
            job_repository=repository,
            analysis_repository=(
                StubAnalysisRepository()
            ),
        )

        with self.assertRaises(
            AnalysisAlreadyActiveError
        ):
            service.ingest(
                owner_steam_id="76561198055629469",
                original_filename="race.dem",
                source=BytesIO(
                    b"demo-content"
                ),
            )

        self.assertEqual(
            len(repository.calls),
            1,
        )

        self.assertEqual(
            list(self.root.iterdir()),
            [],
        )

    def test_ingest_rejects_existing_user_match_and_deletes_new_file(
        self,
    ):
        repository = StubJobRepository()

        analysis_repository = (
            StubAnalysisRepository(
                user_match_position=0,
            )
        )

        service = DemoIngestionService(
            storage=self.storage,
            job_repository=repository,
            analysis_repository=analysis_repository,
        )

        with self.assertRaisesRegex(
            DuplicateDemoError,
            "This demo has already been analyzed",
        ):
            service.ingest(
                owner_steam_id="76561198055629469",
                original_filename="duplicate.dem",
                source=BytesIO(
                    b"demo-content"
                ),
            )

        self.assertEqual(
            repository.calls,
            [],
        )

        self.assertEqual(
            len(analysis_repository.calls),
            1,
        )

        request = analysis_repository.calls[0]

        self.assertEqual(
            request["owner_steam_id"],
            "76561198055629469",
        )

        self.assertEqual(
            len(request["match_id"]),
            64,
        )

        self.assertEqual(
            list(self.root.iterdir()),
            [],
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
            analysis_repository=(
                StubAnalysisRepository()
            ),
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
            analysis_repository=(
                StubAnalysisRepository()
            ),
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

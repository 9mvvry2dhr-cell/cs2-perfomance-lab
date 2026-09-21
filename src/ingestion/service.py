from __future__ import annotations

from threading import Lock
from typing import BinaryIO

from src.database.job_repository import (
    ActiveAnalysisJobConflictError,
    AnalysisJobRepository,
)
from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    LocalDemoStorage,
)


DEFAULT_MAX_ACTIVE_JOBS = 4


class AnalysisQueueFullError(
    RuntimeError
):
    pass


class AnalysisAlreadyActiveError(
    AnalysisQueueFullError
):
    pass


class DuplicateDemoError(
    RuntimeError
):
    pass


class DemoIngestionService:
    _admission_lock = Lock()
    def __init__(
        self,
        *,
        storage: LocalDemoStorage,
        job_repository: AnalysisJobRepository,
        max_active_jobs: int = (
            DEFAULT_MAX_ACTIVE_JOBS
        ),
    ):
        if max_active_jobs <= 0:
            raise ValueError(
                "max_active_jobs must be positive"
            )

        self.storage = storage
        self.job_repository = job_repository
        self.max_active_jobs = (
            max_active_jobs
        )

    def ingest(
        self,
        *,
        owner_steam_id: str,
        original_filename: str,
        source: BinaryIO,
    ) -> AnalysisJob:
        with self._admission_lock:
            owner_active_jobs = (
                self.job_repository
                .count_active_jobs_for_owner(
                    owner_steam_id
                )
            )

            if owner_active_jobs > 0:
                raise AnalysisAlreadyActiveError(
                    "An analysis is already active "
                    "for this Steam account"
                )

            active_jobs = (
                self.job_repository
                .count_active_jobs()
            )

            if (
                active_jobs
                >= self.max_active_jobs
            ):
                raise AnalysisQueueFullError(
                    "Analysis queue is full"
                )

            stored = self.storage.store(
                original_filename=original_filename,
                source=source,
            )

            try:
                completed = (
                    self.job_repository
                    .get_completed_file_for_owner(
                        owner_steam_id,
                        stored.file_sha256,
                    )
                )

                if completed is not None:
                    self.storage.delete(
                        stored.storage_key
                    )

                    return completed

                return self.job_repository.create_job(
                    owner_steam_id=owner_steam_id,
                    original_filename=(
                        stored.original_filename
                    ),
                    storage_key=(
                        stored.storage_key
                    ),
                    file_sha256=(
                        stored.file_sha256
                    ),
                )

            except Exception as exc:
                self.storage.delete(
                    stored.storage_key
                )

                if isinstance(
                    exc,
                    ActiveAnalysisJobConflictError,
                ):
                    raise AnalysisAlreadyActiveError(
                        "An analysis is already active "
                        "for this Steam account"
                    ) from exc

                raise

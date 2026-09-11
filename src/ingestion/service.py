from __future__ import annotations

from typing import BinaryIO

from src.database.job_repository import (
    AnalysisJobRepository,
)
from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    LocalDemoStorage,
)


class DemoIngestionService:
    def __init__(
        self,
        *,
        storage: LocalDemoStorage,
        job_repository: AnalysisJobRepository,
    ):
        self.storage = storage
        self.job_repository = job_repository

    def ingest(
        self,
        *,
        original_filename: str,
        source: BinaryIO,
    ) -> AnalysisJob:
        stored = self.storage.store(
            original_filename=original_filename,
            source=source,
        )

        try:
            return self.job_repository.create_job(
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

        except Exception:
            self.storage.delete(
                stored.storage_key
            )
            raise

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import AnalysisJobModel
from src.domain.jobs import (
    AnalysisJob,
    JobStatus,
)


class AnalysisJobNotFoundError(LookupError):
    pass


class InvalidAnalysisJobTransitionError(ValueError):
    pass


class AnalysisJobRepository:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def create_job(
        self,
        *,
        original_filename: str,
        storage_key: str,
        file_sha256: str,
    ) -> AnalysisJob:
        model = AnalysisJobModel(
            original_filename=original_filename,
            storage_key=storage_key,
            file_sha256=file_sha256,
        )

        try:
            self.session.add(model)
            self.session.commit()
            self.session.refresh(model)

            return self._to_domain(
                model
            )

        except Exception:
            self.session.rollback()
            raise

    def get_job(
        self,
        job_id: str,
    ) -> AnalysisJob | None:
        model = self.session.get(
            AnalysisJobModel,
            job_id,
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def claim_next_job(
        self,
    ) -> AnalysisJob | None:
        try:
            stmt = (
                select(AnalysisJobModel)
                .where(
                    AnalysisJobModel.status
                    == "queued"
                )
                .order_by(
                    AnalysisJobModel.created_at,
                    AnalysisJobModel.id,
                )
                .limit(1)
                .with_for_update(
                    skip_locked=True
                )
            )

            model = self.session.scalar(
                stmt
            )

            if model is None:
                self.session.rollback()
                return None

            model.status = "processing"
            model.started_at = datetime.now(
                timezone.utc
            )
            model.finished_at = None
            model.error = None

            self.session.commit()
            self.session.refresh(model)

            return self._to_domain(
                model
            )

        except Exception:
            self.session.rollback()
            raise

    def mark_processing(
        self,
        job_id: str,
    ) -> AnalysisJob:
        try:
            model = self._get_for_update(
                job_id
            )

            self._require_transition(
                model,
                expected="queued",
                target="processing",
            )

            model.status = "processing"
            model.started_at = datetime.now(
                timezone.utc
            )
            model.finished_at = None
            model.error = None

            self.session.commit()
            self.session.refresh(model)

            return self._to_domain(
                model
            )

        except Exception:
            self.session.rollback()
            raise

    def mark_completed(
        self,
        job_id: str,
        *,
        match_id: str,
    ) -> AnalysisJob:
        try:
            model = self._get_for_update(
                job_id
            )

            self._require_transition(
                model,
                expected="processing",
                target="completed",
            )

            model.status = "completed"
            model.match_id = match_id
            model.error = None
            model.finished_at = datetime.now(
                timezone.utc
            )

            self.session.commit()
            self.session.refresh(model)

            return self._to_domain(
                model
            )

        except Exception:
            self.session.rollback()
            raise

    def mark_failed(
        self,
        job_id: str,
        *,
        error: str,
    ) -> AnalysisJob:
        error = error.strip()

        if not error:
            raise ValueError(
                "error must not be empty"
            )

        try:
            model = self._get_for_update(
                job_id
            )

            self._require_transition(
                model,
                expected="processing",
                target="failed",
            )

            model.status = "failed"
            model.match_id = None
            model.error = error
            model.finished_at = datetime.now(
                timezone.utc
            )

            self.session.commit()
            self.session.refresh(model)

            return self._to_domain(
                model
            )

        except Exception:
            self.session.rollback()
            raise

    def _get_for_update(
        self,
        job_id: str,
    ) -> AnalysisJobModel:
        stmt = (
            select(AnalysisJobModel)
            .where(
                AnalysisJobModel.id == job_id
            )
            .with_for_update()
        )

        model = self.session.scalar(
            stmt
        )

        if model is None:
            raise AnalysisJobNotFoundError(
                f"Analysis job not found: {job_id}"
            )

        return model

    @staticmethod
    def _require_transition(
        model: AnalysisJobModel,
        *,
        expected: str,
        target: str,
    ) -> None:
        if model.status != expected:
            raise InvalidAnalysisJobTransitionError(
                "Invalid analysis job transition: "
                f"{model.status} -> {target}; "
                f"expected current status {expected}"
            )

    @staticmethod
    def _to_domain(
        model: AnalysisJobModel,
    ) -> AnalysisJob:
        return AnalysisJob(
            id=model.id,
            status=cast(
                JobStatus,
                model.status,
            ),
            original_filename=(
                model.original_filename
            ),
            storage_key=model.storage_key,
            file_sha256=model.file_sha256,
            match_id=model.match_id,
            error=model.error,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

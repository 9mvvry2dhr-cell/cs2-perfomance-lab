from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from src.database.models import (
    AnalysisJobModel,
    BugReportModel,
    UserMatchModel,
)
from src.domain.bug_reports import BugReport


VALID_BUG_REPORT_CATEGORIES = frozenset(
    {
        "analysis",
        "statistics",
        "ai",
        "ui",
        "other",
    }
)


class BugReportReferenceError(
    ValueError
):
    pass


class BugReportRepository:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def create_report(
        self,
        *,
        owner_steam_id: str,
        category: str,
        message: str,
        match_id: str | None = None,
        job_id: str | None = None,
    ) -> BugReport:
        owner_steam_id = (
            owner_steam_id.strip()
        )

        category = (
            category.strip().lower()
        )

        message = message.strip()

        match_id = (
            match_id.strip()
            if match_id is not None
            else None
        )

        job_id = (
            job_id.strip()
            if job_id is not None
            else None
        )

        if not owner_steam_id:
            raise ValueError(
                "owner_steam_id must not be empty"
            )

        if (
            category
            not in VALID_BUG_REPORT_CATEGORIES
        ):
            raise ValueError(
                "Unsupported bug report category"
            )

        if len(message) < 5:
            raise ValueError(
                "Bug report message is too short"
            )

        if len(message) > 3000:
            raise ValueError(
                "Bug report message is too long"
            )

        if match_id == "":
            match_id = None

        if job_id == "":
            job_id = None

        if match_id is not None:
            owned_match = self.session.scalar(
                select(
                    exists().where(
                        UserMatchModel.owner_steam_id
                        == owner_steam_id,
                        UserMatchModel.match_id
                        == match_id,
                    )
                )
            )

            if not owned_match:
                raise BugReportReferenceError(
                    "Match is not owned by user"
                )

        if job_id is not None:
            owned_job = self.session.scalar(
                select(
                    exists().where(
                        AnalysisJobModel.id
                        == job_id,
                        AnalysisJobModel.owner_steam_id
                        == owner_steam_id,
                    )
                )
            )

            if not owned_job:
                raise BugReportReferenceError(
                    "Analysis job is not owned by user"
                )

        model = BugReportModel(
            owner_steam_id=owner_steam_id,
            category=category,
            message=message,
            match_id=match_id,
            job_id=job_id,
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

    @staticmethod
    def _to_domain(
        model: BugReportModel,
    ) -> BugReport:
        return BugReport(
            id=model.id,
            owner_steam_id=(
                model.owner_steam_id
            ),
            category=model.category,
            message=model.message,
            match_id=model.match_id,
            job_id=model.job_id,
            created_at=model.created_at,
        )

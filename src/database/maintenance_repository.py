from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from src.database.models import (
    AnalysisJobModel,
    AuthSessionModel,
    BugReportModel,
    MatchModel,
    UserMatchModel,
)


class MaintenanceRepository:
    def __init__(self, session: Session):
        self.session = session

    def purge_expired_or_revoked_sessions(
        self,
        *,
        now: datetime,
    ) -> int:
        try:
            result = self.session.execute(
                delete(AuthSessionModel).where(
                    or_(
                        AuthSessionModel.expires_at <= now,
                        AuthSessionModel.revoked_at.is_not(
                            None
                        ),
                    )
                )
            )

            self.session.commit()

            return int(result.rowcount or 0)

        except Exception:
            self.session.rollback()
            raise

    def purge_finished_analysis_jobs(
        self,
        *,
        finished_before: datetime,
    ) -> int:
        try:
            result = self.session.execute(
                delete(AnalysisJobModel).where(
                    AnalysisJobModel.status.in_(
                        (
                            "completed",
                            "failed",
                        )
                    ),
                    AnalysisJobModel.finished_at.is_not(
                        None
                    ),
                    AnalysisJobModel.finished_at
                    < finished_before,
                )
            )

            self.session.commit()

            return int(result.rowcount or 0)

        except Exception:
            self.session.rollback()
            raise

    def purge_bug_reports(
        self,
        *,
        created_before: datetime,
    ) -> int:
        try:
            result = self.session.execute(
                delete(BugReportModel).where(
                    BugReportModel.created_at
                    < created_before
                )
            )

            self.session.commit()

            return int(result.rowcount or 0)

        except Exception:
            self.session.rollback()
            raise

    def purge_user_matches(
        self,
        *,
        created_before: datetime,
    ) -> int:
        try:
            result = self.session.execute(
                delete(UserMatchModel).where(
                    UserMatchModel.created_at
                    < created_before
                )
            )

            self.session.commit()

            return int(result.rowcount or 0)

        except Exception:
            self.session.rollback()
            raise

    def purge_orphan_matches(
        self,
    ) -> int:
        """
        Delete matches that belong to no retained user.

        An active upload/analysis with the same SHA protects the
        match from deletion. This closes the small window between
        save_analysis() and link_user_match().
        """
        active_job_exists = exists(
            select(AnalysisJobModel.id).where(
                AnalysisJobModel.file_sha256
                == MatchModel.match_id,
                AnalysisJobModel.status.in_(
                    (
                        "queued",
                        "processing",
                    )
                ),
            )
        )

        user_match_exists = exists(
            select(UserMatchModel.match_id).where(
                UserMatchModel.match_id
                == MatchModel.match_id
            )
        )

        try:
            models = list(
                self.session.scalars(
                    select(MatchModel).where(
                        ~user_match_exists,
                        ~active_job_exists,
                    )
                ).all()
            )

            for model in models:
                self.session.delete(model)

            self.session.commit()

            return len(models)

        except Exception:
            self.session.rollback()
            raise

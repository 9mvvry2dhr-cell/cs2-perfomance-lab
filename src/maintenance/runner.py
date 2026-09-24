from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.maintenance_repository import (
    MaintenanceRepository,
)


logger = logging.getLogger(__name__)


DEFAULT_INTERVAL_SECONDS = 3600.0
DEFAULT_JOB_RETENTION_DAYS = 30
DEFAULT_BUG_REPORT_RETENTION_DAYS = 90
DEFAULT_USER_MATCH_RETENTION_DAYS = 90


@dataclass(frozen=True)
class MaintenanceResult:
    sessions_deleted: int
    bug_reports_deleted: int
    jobs_deleted: int
    user_matches_deleted: int
    matches_deleted: int


def run_maintenance_once(
    *,
    session_factory: sessionmaker[Session],
    now: datetime | None = None,
    job_retention_days: int = (
        DEFAULT_JOB_RETENTION_DAYS
    ),
    bug_report_retention_days: int = (
        DEFAULT_BUG_REPORT_RETENTION_DAYS
    ),
    user_match_retention_days: int = (
        DEFAULT_USER_MATCH_RETENTION_DAYS
    ),
    repository_factory: Callable[
        [Session],
        MaintenanceRepository,
    ] = MaintenanceRepository,
) -> MaintenanceResult:
    if job_retention_days <= 0:
        raise ValueError(
            "job_retention_days must be positive"
        )

    if bug_report_retention_days <= 0:
        raise ValueError(
            "bug_report_retention_days must be positive"
        )

    if user_match_retention_days <= 0:
        raise ValueError(
            "user_match_retention_days must be positive"
        )

    now = now or datetime.now(timezone.utc)

    session = session_factory()

    try:
        repository = repository_factory(
            session
        )

        sessions_deleted = (
            repository
            .purge_expired_or_revoked_sessions(
                now=now
            )
        )

        bug_reports_deleted = (
            repository
            .purge_bug_reports(
                created_before=(
                    now
                    - timedelta(
                        days=bug_report_retention_days
                    )
                )
            )
        )

        jobs_deleted = (
            repository
            .purge_finished_analysis_jobs(
                finished_before=(
                    now
                    - timedelta(
                        days=job_retention_days
                    )
                )
            )
        )

        user_matches_deleted = (
            repository
            .purge_user_matches(
                created_before=(
                    now
                    - timedelta(
                        days=user_match_retention_days
                    )
                )
            )
        )

        matches_deleted = (
            repository
            .purge_orphan_matches()
        )

        return MaintenanceResult(
            sessions_deleted=sessions_deleted,
            bug_reports_deleted=(
                bug_reports_deleted
            ),
            jobs_deleted=jobs_deleted,
            user_matches_deleted=(
                user_matches_deleted
            ),
            matches_deleted=matches_deleted,
        )

    finally:
        session.close()


def run_forever(
    run_once: Callable[
        [],
        MaintenanceResult,
    ],
    *,
    interval_seconds: float = (
        DEFAULT_INTERVAL_SECONDS
    ),
    sleep: Callable[
        [float],
        None,
    ] = time.sleep,
) -> None:
    if interval_seconds <= 0:
        raise ValueError(
            "interval_seconds must be positive"
        )

    while True:
        try:
            result = run_once()

            logger.info(
                "Maintenance completed: "
                "sessions=%s bug_reports=%s "
                "jobs=%s user_matches=%s matches=%s",
                result.sessions_deleted,
                result.bug_reports_deleted,
                result.jobs_deleted,
                result.user_matches_deleted,
                result.matches_deleted,
            )

        except Exception:
            logger.exception(
                "Maintenance cycle failed"
            )

        sleep(interval_seconds)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s: "
            "%(message)s"
        ),
    )

    interval_seconds = float(
        os.environ.get(
            "MAINTENANCE_INTERVAL_SECONDS",
            str(DEFAULT_INTERVAL_SECONDS),
        )
    )

    job_retention_days = int(
        os.environ.get(
            "ANALYSIS_JOB_RETENTION_DAYS",
            str(DEFAULT_JOB_RETENTION_DAYS),
        )
    )

    bug_report_retention_days = int(
        os.environ.get(
            "BUG_REPORT_RETENTION_DAYS",
            str(
                DEFAULT_BUG_REPORT_RETENTION_DAYS
            ),
        )
    )

    user_match_retention_days = int(
        os.environ.get(
            "USER_MATCH_RETENTION_DAYS",
            str(
                DEFAULT_USER_MATCH_RETENTION_DAYS
            ),
        )
    )

    engine = create_db_engine()

    session_factory = (
        create_session_factory(
            engine
        )
    )

    logger.info(
        "Maintenance service started: "
        "interval=%.0fs jobs=%sd "
        "bug_reports=%sd user_matches=%sd",
        interval_seconds,
        job_retention_days,
        bug_report_retention_days,
        user_match_retention_days,
    )

    try:
        run_forever(
            lambda: run_maintenance_once(
                session_factory=session_factory,
                job_retention_days=(
                    job_retention_days
                ),
                bug_report_retention_days=(
                    bug_report_retention_days
                ),
                user_match_retention_days=(
                    user_match_retention_days
                ),
            ),
            interval_seconds=interval_seconds,
        )

    except KeyboardInterrupt:
        logger.info(
            "Maintenance service stopped"
        )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

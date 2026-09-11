from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.job_repository import (
    AnalysisJobRepository,
)
from src.database.repository import (
    AnalysisRepository,
)
from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    LocalDemoStorage,
)
from src.workers.analysis_worker import (
    AnalysisWorker,
)


logger = logging.getLogger(__name__)

DEFAULT_POLL_SECONDS = 2.0


def process_next_job(
    *,
    session_factory: sessionmaker[Session],
    storage: LocalDemoStorage,
) -> AnalysisJob | None:
    session = session_factory()

    try:
        worker = AnalysisWorker(
            storage=storage,
            job_repository=(
                AnalysisJobRepository(
                    session
                )
            ),
            analysis_repository=(
                AnalysisRepository(
                    session
                )
            ),
        )

        return worker.process_next()

    finally:
        session.close()


def run_forever(
    process_next: Callable[
        [],
        AnalysisJob | None,
    ],
    *,
    poll_seconds: float = (
        DEFAULT_POLL_SECONDS
    ),
    sleep: Callable[
        [float],
        None,
    ] = time.sleep,
) -> None:
    if poll_seconds <= 0:
        raise ValueError(
            "poll_seconds must be positive"
        )

    while True:
        try:
            job = process_next()

        except Exception:
            logger.exception(
                "Analysis job failed"
            )

            sleep(
                poll_seconds
            )
            continue

        if job is None:
            sleep(
                poll_seconds
            )
            continue

        logger.info(
            "Analysis job completed: "
            "%s -> %s",
            job.id,
            job.match_id,
        )


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

    storage_root = Path(
        os.environ.get(
            "DEMO_STORAGE_DIR",
            "data/uploads",
        )
    )

    poll_seconds = float(
        os.environ.get(
            "ANALYSIS_WORKER_POLL_SECONDS",
            str(DEFAULT_POLL_SECONDS),
        )
    )

    engine = create_db_engine()

    session_factory = (
        create_session_factory(
            engine
        )
    )

    storage = LocalDemoStorage(
        storage_root
    )

    logger.info(
        "Analysis worker started"
    )

    try:
        run_forever(
            lambda: process_next_job(
                session_factory=(
                    session_factory
                ),
                storage=storage,
            ),
            poll_seconds=poll_seconds,
        )

    except KeyboardInterrupt:
        logger.info(
            "Analysis worker stopped"
        )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

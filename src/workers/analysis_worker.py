from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from src.database.job_repository import (
    AnalysisJobRepository,
)
from src.database.repository import (
    AnalysisRepository,
)
from src.domain.analysis import (
    MatchAnalysis,
    build_match_analysis,
)
from src.domain.jobs import AnalysisJob
from src.ingestion.storage import (
    LocalDemoStorage,
)
from src.metrics.splits import (
    calculate_split_metrics,
)
from src.parsing.demo_parser import DemoParser


logger = logging.getLogger(__name__)


class DemoOwnerNotFoundError(ValueError):
    pass


def analyze_demo_file(
    demo_path: Path,
) -> MatchAnalysis:
    total_started = time.perf_counter()

    parser = DemoParser(
        str(demo_path)
    )

    parse_started = time.perf_counter()

    match = parser.parse()

    parse_seconds = (
        time.perf_counter()
        - parse_started
    )

    splits_started = time.perf_counter()

    splits = calculate_split_metrics(
        parser.raw_parser,
        [
            player.steam_id
            for player in match.players
        ],
        side_events=parser.side_events,
        survival_events=parser.survival_events,
        kast_events=parser.kast_events,
        entry_events=parser.entry_events,
    )

    splits_seconds = (
        time.perf_counter()
        - splits_started
    )

    build_started = time.perf_counter()

    analysis = build_match_analysis(
        match,
        splits,
    )

    build_seconds = (
        time.perf_counter()
        - build_started
    )

    total_seconds = (
        time.perf_counter()
        - total_started
    )

    logger.info(
        "ANALYSIS_TIMING "
        "file=%s "
        "parse=%.2fs "
        "splits=%.2fs "
        "build=%.2fs "
        "total=%.2fs",
        demo_path.name,
        parse_seconds,
        splits_seconds,
        build_seconds,
        total_seconds,
    )

    return analysis


class AnalysisWorker:
    def __init__(
        self,
        *,
        storage: LocalDemoStorage,
        job_repository: AnalysisJobRepository,
        analysis_repository: AnalysisRepository,
        analyzer: Callable[
            [Path],
            MatchAnalysis,
        ] = analyze_demo_file,
    ):
        self.storage = storage
        self.job_repository = (
            job_repository
        )
        self.analysis_repository = (
            analysis_repository
        )
        self.analyzer = analyzer

    def process(
        self,
        job_id: str,
    ) -> AnalysisJob:
        job = (
            self.job_repository
            .mark_processing(job_id)
        )

        return self._process_claimed(
            job
        )

    def process_next(
        self,
    ) -> AnalysisJob | None:
        job = (
            self.job_repository
            .claim_next_job()
        )

        if job is None:
            return None

        return self._process_claimed(
            job
        )

    def _process_claimed(
        self,
        job: AnalysisJob,
    ) -> AnalysisJob:
        try:
            demo_path = (
                self.storage.path_for(
                    job.storage_key
                )
            )

            if not demo_path.is_file():
                raise FileNotFoundError(
                    "Stored demo file not found"
                )

            analysis = self.analyzer(
                demo_path
            )

            if (
                job.owner_steam_id is not None
                and not any(
                    player.steam_id
                    == job.owner_steam_id
                    for player in analysis.players
                )
            ):
                raise DemoOwnerNotFoundError(
                    "Authenticated Steam account "
                    "was not found in demo"
                )

            # Uploaded demos need a stable identity independent
            # of the user-provided filename. The content hash is
            # deterministic and prevents different files with the
            # same name from overwriting each other.
            analysis = replace(
                analysis,
                match_id=job.file_sha256,
            )

            self.analysis_repository.save_analysis(
                analysis
            )

            completed_job = (
                self.job_repository
                .mark_completed(
                    job.id,
                    match_id=(
                        analysis.match_id
                    ),
                )
            )

        except Exception as exc:
            error = (
                "Authenticated Steam account "
                "was not found in demo"
                if isinstance(
                    exc,
                    DemoOwnerNotFoundError,
                )
                else "Analysis failed"
            )

            self.job_repository.mark_failed(
                job.id,
                error=error,
            )

            try:
                self.storage.delete(
                    job.storage_key
                )
            except Exception:
                logger.exception(
                    "Failed to delete failed job demo",
                    extra={
                        "job_id": job.id,
                        "storage_key": (
                            job.storage_key
                        ),
                    },
                )

            raise

        try:
            self.storage.delete(
                job.storage_key
            )
        except Exception:
            logger.exception(
                "Failed to delete completed job demo",
                extra={
                    "job_id": job.id,
                    "storage_key": (
                        job.storage_key
                    ),
                },
            )

        return completed_job

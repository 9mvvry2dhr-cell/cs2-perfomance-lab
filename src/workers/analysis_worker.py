from __future__ import annotations

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


def analyze_demo_file(
    demo_path: Path,
) -> MatchAnalysis:
    parser = DemoParser(
        str(demo_path)
    )

    match = parser.parse()

    splits = calculate_split_metrics(
        parser.raw_parser,
        [
            player.steam_id
            for player in match.players
        ],
    )

    return build_match_analysis(
        match,
        splits,
    )


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

            # Uploaded demos are stored under a random UUID.
            # Preserve the original filename-based match identity
            # used by DemoParser before the ingestion layer existed.
            analysis = replace(
                analysis,
                match_id=Path(
                    job.original_filename
                ).stem,
            )

            self.analysis_repository.save_analysis(
                analysis
            )

            return (
                self.job_repository
                .mark_completed(
                    job.id,
                    match_id=(
                        analysis.match_id
                    ),
                )
            )

        except Exception:
            self.job_repository.mark_failed(
                job.id,
                error="Analysis failed",
            )
            raise

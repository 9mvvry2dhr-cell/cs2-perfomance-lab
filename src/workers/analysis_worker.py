from __future__ import annotations

import logging
import multiprocessing
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from src.audit import audit_event
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
from src.metrics.duel import calculate_duel_analysis
from src.metrics.utility import (
    calculate_utility_analysis,
)
from src.metrics.match_facts import (
    build_match_facts,
    encode_match_facts,
)
from src.metrics.splits import (
    calculate_split_metrics,
)
from src.parsing.demo_parser import DemoParser


logger = logging.getLogger(__name__)


DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 600.0


class DemoOwnerNotFoundError(ValueError):
    pass


class AnalysisTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True)
class DemoAnalysisResult:
    analysis: MatchAnalysis
    match_facts_payload: bytes
    match_facts_version: int
    match_facts_capabilities: tuple[str, ...]


class MatchFactsBuildError(RuntimeError):
    pass


def _analyze_demo_file(
    demo_path: Path,
    *,
    capture_match_facts: bool,
) -> MatchAnalysis | DemoAnalysisResult:
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

    player_steam_ids = [
        player.steam_id
        for player in match.players
    ]

    splits_started = time.perf_counter()

    splits = calculate_split_metrics(
        parser.raw_parser,
        player_steam_ids,
        side_events=parser.side_events,
        survival_events=parser.survival_events,
        kast_events=parser.kast_events,
        entry_events=parser.entry_events,
    )

    splits_seconds = (
        time.perf_counter()
        - splits_started
    )

    (
        duels,
        duel_episodes,
    ) = calculate_duel_analysis(
        parser.raw_parser,
        player_steam_ids,
    )

    _utility_metrics, utility_rounds = (
        calculate_utility_analysis(
            parser.raw_parser
        )
    )

    build_started = time.perf_counter()

    analysis = build_match_analysis(
        match,
        splits,
        duels,
        duel_episodes,
        utility_rounds_by_player=utility_rounds,
    )

    build_seconds = (
        time.perf_counter()
        - build_started
    )

    facts_seconds = 0.0
    facts = None
    payload = None

    if capture_match_facts:
        facts_started = time.perf_counter()

        try:
            facts = build_match_facts(
                parser.raw_parser,
                player_steam_ids,
            )

            payload = encode_match_facts(
                facts
            )

        except Exception as exc:
            raise MatchFactsBuildError(
                "Failed to build Match Facts"
            ) from exc

        facts_seconds = (
            time.perf_counter()
            - facts_started
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
        "facts=%.2fs "
        "total=%.2fs",
        demo_path.name,
        parse_seconds,
        splits_seconds,
        build_seconds,
        facts_seconds,
        total_seconds,
    )

    if not capture_match_facts:
        return analysis

    assert facts is not None
    assert payload is not None

    return DemoAnalysisResult(
        analysis=analysis,
        match_facts_payload=payload,
        match_facts_version=int(
            facts["facts_version"]
        ),
        match_facts_capabilities=tuple(
            str(item)
            for item in facts["capabilities"]
        ),
    )


def analyze_demo_file(
    demo_path: Path,
) -> MatchAnalysis:
    result = _analyze_demo_file(
        demo_path,
        capture_match_facts=False,
    )

    assert isinstance(
        result,
        MatchAnalysis,
    )

    return result


def analyze_demo_file_with_facts(
    demo_path: Path,
) -> DemoAnalysisResult:
    result = _analyze_demo_file(
        demo_path,
        capture_match_facts=True,
    )

    assert isinstance(
        result,
        DemoAnalysisResult,
    )

    return result

def _analysis_subprocess(
    demo_path: str,
    connection,
) -> None:
    """
    Run parsing in an isolated process.

    If demoparser2 hangs, the parent worker can terminate
    this process without killing the queue worker itself.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s: "
            "%(message)s"
        ),
    )

    try:
        result = analyze_demo_file_with_facts(
            Path(demo_path)
        )

        connection.send(
            (
                "ok",
                result,
            )
        )

    except MatchFactsBuildError as exc:
        logger.exception(
            "Match Facts build failed"
        )

        try:
            connection.send(
                (
                    "facts_error",
                    str(exc),
                )
            )

        except Exception:
            pass

    except BaseException as exc:
        logger.exception(
            "Analysis subprocess failed"
        )

        try:
            connection.send(
                (
                    "error",
                    type(exc).__name__,
                    str(exc),
                )
            )

        except Exception:
            pass

    finally:
        connection.close()


def _terminate_process(
    process,
) -> None:
    if not process.is_alive():
        process.join(
            timeout=0
        )
        return

    process.terminate()

    process.join(
        timeout=5.0
    )

    if process.is_alive():
        process.kill()

        process.join(
            timeout=5.0
        )


def analyze_demo_file_with_timeout(
    demo_path: Path,
    *,
    timeout_seconds: float = (
        DEFAULT_ANALYSIS_TIMEOUT_SECONDS
    ),
) -> DemoAnalysisResult:
    """
    Execute one demo analysis in a disposable child process.

    The parent worker remains able to continue processing the
    queue even if demoparser2 becomes permanently stuck.
    """

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be positive"
        )

    context = multiprocessing.get_context(
        "spawn"
    )

    parent_connection, child_connection = (
        context.Pipe(
            duplex=False
        )
    )

    process = context.Process(
        target=_analysis_subprocess,
        args=(
            str(demo_path),
            child_connection,
        ),
        name="cs2-demo-analysis",
    )

    process.start()

    # Parent never writes to this end.
    child_connection.close()

    try:
        if not parent_connection.poll(
            timeout_seconds
        ):
            logger.error(
                "Analysis timed out after %.1fs: %s",
                timeout_seconds,
                demo_path.name,
            )

            _terminate_process(
                process
            )

            raise AnalysisTimeoutError(
                "Demo analysis exceeded "
                f"{timeout_seconds:.0f} seconds"
            )

        try:
            message = (
                parent_connection.recv()
            )

        except EOFError as exc:
            process.join(
                timeout=1.0
            )

            raise RuntimeError(
                "Analysis subprocess exited "
                "without a result"
            ) from exc

        process.join(
            timeout=5.0
        )

        if process.is_alive():
            _terminate_process(
                process
            )

            raise RuntimeError(
                "Analysis subprocess did not exit "
                "after returning a result"
            )

        if (
            not isinstance(message, tuple)
            or not message
        ):
            raise RuntimeError(
                "Invalid analysis subprocess result"
            )

        status = message[0]

        if status == "ok":
            return message[1]

        if status == "facts_error":
            error_message = (
                message[1]
                if len(message) > 1
                else "Match Facts build failed"
            )

            raise MatchFactsBuildError(
                error_message
            )

        if status == "error":
            error_type = (
                message[1]
                if len(message) > 1
                else "UnknownError"
            )

            error_message = (
                message[2]
                if len(message) > 2
                else ""
            )

            raise RuntimeError(
                "Analysis subprocess failed: "
                f"{error_type}: "
                f"{error_message}"
            )

        raise RuntimeError(
            "Unknown analysis subprocess status: "
            f"{status}"
        )

    finally:
        parent_connection.close()

        if process.is_alive():
            _terminate_process(
                process
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
            MatchAnalysis | DemoAnalysisResult,
        ] = analyze_demo_file_with_facts,
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
        preserve_demo_on_failure = False

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

            analyzer_result = self.analyzer(
                demo_path
            )

            if isinstance(
                analyzer_result,
                DemoAnalysisResult,
            ):
                analysis = (
                    analyzer_result.analysis
                )

                match_facts_kwargs = {
                    "match_facts_payload": (
                        analyzer_result
                        .match_facts_payload
                    ),
                    "match_facts_version": (
                        analyzer_result
                        .match_facts_version
                    ),
                    "match_facts_capabilities": list(
                        analyzer_result
                        .match_facts_capabilities
                    ),
                }

            else:
                analysis = analyzer_result
                match_facts_kwargs = {}

            owner_player_position = None

            if job.owner_steam_id is not None:
                owner_player_position = next(
                    (
                        position
                        for position, player
                        in enumerate(analysis.players)
                        if player.steam_id
                        == job.owner_steam_id
                    ),
                    None,
                )

                if owner_player_position is None:
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

            preserve_demo_on_failure = True

            self.analysis_repository.save_analysis(
                analysis,
                **match_facts_kwargs,
            )

            preserve_demo_on_failure = False

            if (
                job.owner_steam_id is not None
                and owner_player_position is not None
            ):
                self.analysis_repository.link_user_match(
                    owner_steam_id=job.owner_steam_id,
                    match_id=analysis.match_id,
                    player_position=owner_player_position,
                    match_source=job.match_source,
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

            audit_event(
                "analysis.completed",
                steam_id=job.owner_steam_id,
                job_id=job.id,
                match_id=analysis.match_id,
                match_source=job.match_source,
            )

            if job.owner_steam_id is not None:
                try:
                    founding_number = (
                        self.job_repository
                        .claim_founding_tester(
                            job.owner_steam_id
                        )
                    )

                    if founding_number is not None:
                        audit_event(
                            "founding_tester.awarded",
                            steam_id=job.owner_steam_id,
                            job_id=job.id,
                            match_id=analysis.match_id,
                            founding_number=(
                                founding_number
                            ),
                            premium_days=30,
                        )

                except Exception:
                    logger.exception(
                        "Failed to award "
                        "Founding Tester",
                        extra={
                            "job_id": job.id,
                            "steam_id": (
                                job.owner_steam_id
                            ),
                        },
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

            audit_event(
                "analysis.failed",
                steam_id=job.owner_steam_id,
                status="failed",
                job_id=job.id,
                match_source=job.match_source,
                reason=(
                    "owner_not_found"
                    if isinstance(
                        exc,
                        DemoOwnerNotFoundError,
                    )
                    else "analysis_failed"
                ),
            )

            if (
                preserve_demo_on_failure
                or isinstance(
                    exc,
                    MatchFactsBuildError,
                )
            ):
                raise

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

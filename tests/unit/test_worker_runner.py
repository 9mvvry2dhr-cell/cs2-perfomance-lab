import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.workers.runner import (
    DEFAULT_STALE_SECONDS,
    process_next_job,
    run_forever,
)


class WorkerRunnerTest(
    unittest.TestCase
):
    def test_default_stale_timeout_is_three_minutes(
        self,
    ):
        self.assertEqual(
            DEFAULT_STALE_SECONDS,
            180.0,
        )

    def test_process_next_job_requeues_stale_jobs_before_processing(
        self,
    ):
        session = Mock()
        session_factory = Mock(
            return_value=session
        )
        storage = Mock()

        job_repository = Mock()
        job_repository.requeue_stale_processing_jobs.return_value = 1

        completed_job = Mock()

        worker = Mock()
        worker.process_next.return_value = (
            completed_job
        )

        before = datetime.now(
            timezone.utc
        )

        with (
            patch(
                "src.workers.runner.AnalysisJobRepository",
                return_value=job_repository,
            ) as job_repository_class,
            patch(
                "src.workers.runner.AnalysisRepository",
            ) as analysis_repository_class,
            patch(
                "src.workers.runner.AnalysisWorker",
                return_value=worker,
            ) as worker_class,
        ):
            result = process_next_job(
                session_factory=session_factory,
                storage=storage,
                stale_seconds=3600.0,
            )

        after = datetime.now(
            timezone.utc
        )

        stale_before = (
            job_repository
            .requeue_stale_processing_jobs
            .call_args
            .kwargs["stale_before"]
        )

        self.assertGreaterEqual(
            stale_before,
            before - timedelta(hours=1),
        )

        self.assertLessEqual(
            stale_before,
            after - timedelta(hours=1),
        )

        session_factory.assert_called_once_with()

        job_repository_class.assert_called_once_with(
            session
        )

        analysis_repository_class.assert_called_once_with(
            session
        )

        job_repository.requeue_stale_processing_jobs.assert_called_once()

        worker_class.assert_called_once()

        worker.process_next.assert_called_once_with()

        session.close.assert_called_once_with()

        self.assertIs(
            result,
            completed_job,
        )

    def test_process_next_job_rejects_invalid_stale_timeout(
        self,
    ):
        session_factory = Mock()

        with self.assertRaises(
            ValueError
        ):
            process_next_job(
                session_factory=session_factory,
                storage=Mock(),
                stale_seconds=0,
            )

        session_factory.assert_not_called()

    def test_empty_queue_sleeps_and_keeps_polling(
        self,
    ):
        calls = 0
        sleeps = []

        def process_next():
            nonlocal calls
            calls += 1

            if calls == 1:
                return None

            raise KeyboardInterrupt

        with self.assertRaises(
            KeyboardInterrupt
        ):
            run_forever(
                process_next,
                poll_seconds=3.0,
                sleep=sleeps.append,
            )

        self.assertEqual(
            calls,
            2,
        )

        self.assertEqual(
            sleeps,
            [3.0],
        )

    def test_failed_job_does_not_stop_worker(
        self,
    ):
        calls = 0
        sleeps = []

        def process_next():
            nonlocal calls
            calls += 1

            if calls == 1:
                raise RuntimeError(
                    "parser failed"
                )

            raise KeyboardInterrupt

        with self.assertRaises(
            KeyboardInterrupt
        ):
            run_forever(
                process_next,
                poll_seconds=2.0,
                sleep=sleeps.append,
            )

        self.assertEqual(
            calls,
            2,
        )

        self.assertEqual(
            sleeps,
            [2.0],
        )

    def test_successful_job_immediately_checks_next_job(
        self,
    ):
        calls = 0
        sleeps = []

        class CompletedJob:
            id = "job-001"
            match_id = "match-001"

        def process_next():
            nonlocal calls
            calls += 1

            if calls == 1:
                return CompletedJob()

            raise KeyboardInterrupt

        with self.assertRaises(
            KeyboardInterrupt
        ):
            run_forever(
                process_next,
                sleep=sleeps.append,
            )

        self.assertEqual(
            calls,
            2,
        )

        self.assertEqual(
            sleeps,
            [],
        )

    def test_rejects_invalid_poll_interval(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            run_forever(
                lambda: None,
                poll_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()

import unittest

from src.workers.runner import (
    run_forever,
)


class WorkerRunnerTest(
    unittest.TestCase
):
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

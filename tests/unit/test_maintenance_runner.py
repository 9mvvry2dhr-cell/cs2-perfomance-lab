import unittest
from datetime import datetime, timedelta, timezone

from src.maintenance.runner import (
    MaintenanceResult,
    run_forever,
    run_maintenance_once,
)


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeMaintenanceRepository:
    instances = []

    def __init__(self, session):
        self.session = session
        self.calls = []

        self.__class__.instances.append(
            self
        )

    def purge_expired_or_revoked_sessions(
        self,
        *,
        now,
    ):
        self.calls.append(
            ("sessions", now)
        )
        return 1

    def purge_finished_analysis_jobs(
        self,
        *,
        finished_before,
    ):
        self.calls.append(
            ("jobs", finished_before)
        )
        return 2

    def purge_user_matches(
        self,
        *,
        created_before,
    ):
        self.calls.append(
            ("user_matches", created_before)
        )
        return 3

    def purge_orphan_matches(self):
        self.calls.append(
            ("matches", None)
        )
        return 4


class MaintenanceRunnerTest(
    unittest.TestCase
):
    def setUp(self):
        FakeMaintenanceRepository.instances = []

        self.now = datetime(
            2026,
            9,
            24,
            10,
            0,
            tzinfo=timezone.utc,
        )

    def test_run_once_uses_expected_cutoffs(
        self,
    ):
        session = FakeSession()

        result = run_maintenance_once(
            session_factory=lambda: session,
            now=self.now,
            job_retention_days=30,
            user_match_retention_days=90,
            repository_factory=(
                FakeMaintenanceRepository
            ),
        )

        self.assertEqual(
            result,
            MaintenanceResult(
                sessions_deleted=1,
                jobs_deleted=2,
                user_matches_deleted=3,
                matches_deleted=4,
            ),
        )

        repository = (
            FakeMaintenanceRepository
            .instances[0]
        )

        self.assertEqual(
            repository.calls,
            [
                (
                    "sessions",
                    self.now,
                ),
                (
                    "jobs",
                    self.now
                    - timedelta(days=30),
                ),
                (
                    "user_matches",
                    self.now
                    - timedelta(days=90),
                ),
                (
                    "matches",
                    None,
                ),
            ],
        )

        self.assertTrue(
            session.closed
        )

    def test_run_once_closes_session_on_error(
        self,
    ):
        session = FakeSession()

        class FailingRepository(
            FakeMaintenanceRepository
        ):
            def purge_finished_analysis_jobs(
                self,
                *,
                finished_before,
            ):
                raise RuntimeError(
                    "database failed"
                )

        with self.assertRaisesRegex(
            RuntimeError,
            "database failed",
        ):
            run_maintenance_once(
                session_factory=lambda: session,
                now=self.now,
                repository_factory=(
                    FailingRepository
                ),
            )

        self.assertTrue(
            session.closed
        )

    def test_retention_days_must_be_positive(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            run_maintenance_once(
                session_factory=FakeSession,
                now=self.now,
                job_retention_days=0,
            )

        with self.assertRaises(
            ValueError
        ):
            run_maintenance_once(
                session_factory=FakeSession,
                now=self.now,
                user_match_retention_days=0,
            )

    def test_run_forever_sleeps_after_cycle(
        self,
    ):
        calls = []

        def run_once():
            calls.append("run")

            return MaintenanceResult(
                sessions_deleted=0,
                jobs_deleted=0,
                user_matches_deleted=0,
                matches_deleted=0,
            )

        def sleep(seconds):
            calls.append(
                ("sleep", seconds)
            )

            raise StopIteration

        with self.assertRaises(
            StopIteration
        ):
            run_forever(
                run_once,
                interval_seconds=123,
                sleep=sleep,
            )

        self.assertEqual(
            calls,
            [
                "run",
                ("sleep", 123),
            ],
        )


if __name__ == "__main__":
    unittest.main()

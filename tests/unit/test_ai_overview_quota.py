import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.ai_overview_quota_repository import (
    AIOverviewQuotaRepository,
    AIOverviewRateLimitError,
)
from src.database.models import (
    Base,
    UserModel,
)


class AIOverviewQuotaRepositoryTest(
    unittest.TestCase
):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
        )

        Base.metadata.create_all(
            self.engine
        )

        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

        self.session = self.Session()

        self.user = UserModel(
            steam_id="76561198055629469"
        )

        self.session.add(
            self.user
        )

        self.session.commit()

        self.repository = (
            AIOverviewQuotaRepository(
                self.session,
                cooldown_days=30,
            )
        )

        self.now = datetime(
            2026,
            9,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def tearDown(self):
        self.session.close()

        Base.metadata.drop_all(
            self.engine
        )

        self.engine.dispose()

    def test_available_before_first_generation(self):
        status = (
            self.repository
            .get_status(
                self.user.steam_id,
                now=self.now,
            )
        )

        self.assertTrue(
            status.available
        )

        self.assertFalse(
            status.has_cached_report
        )

        self.assertIsNone(
            status.next_available_at
        )

    def test_successful_generation_starts_30_day_cooldown(self):
        self.repository.reserve_generation(
            self.user.steam_id,
            now=self.now,
        )

        self.repository.commit_success(
            {
                "summary": "cached",
            }
        )

        status = (
            self.repository
            .get_status(
                self.user.steam_id,
                now=(
                    self.now
                    + timedelta(days=1)
                ),
            )
        )

        self.assertFalse(
            status.available
        )

        self.assertTrue(
            status.has_cached_report
        )

        self.assertEqual(
            status.next_available_at,
            self.now
            + timedelta(days=30),
        )

        self.assertEqual(
            self.repository
            .get_cached_response(
                self.user.steam_id
            ),
            {
                "summary": "cached",
            },
        )

    def test_failed_generation_does_not_consume_quota(self):
        self.repository.reserve_generation(
            self.user.steam_id,
            now=self.now,
        )

        self.repository.cancel_generation()

        status = (
            self.repository
            .get_status(
                self.user.steam_id,
                now=(
                    self.now
                    + timedelta(minutes=1)
                ),
            )
        )

        self.assertTrue(
            status.available
        )

        self.assertFalse(
            status.has_cached_report
        )

    def test_second_generation_inside_window_is_rejected(self):
        self.repository.reserve_generation(
            self.user.steam_id,
            now=self.now,
        )

        self.repository.commit_success(
            {
                "summary": "cached",
            }
        )

        with self.assertRaises(
            AIOverviewRateLimitError
        ) as context:
            self.repository.reserve_generation(
                self.user.steam_id,
                now=(
                    self.now
                    + timedelta(days=29)
                ),
            )

        self.assertEqual(
            context.exception.next_available_at,
            self.now
            + timedelta(days=30),
        )

    def test_zero_day_cooldown_keeps_local_testing_unlimited(self):
        repository = (
            AIOverviewQuotaRepository(
                self.session,
                cooldown_days=0,
            )
        )

        repository.reserve_generation(
            self.user.steam_id,
            now=self.now,
        )

        repository.commit_success(
            {
                "summary": "first",
            }
        )

        status = repository.get_status(
            self.user.steam_id,
            now=(
                self.now
                + timedelta(seconds=1)
            ),
        )

        self.assertTrue(
            status.available
        )


if __name__ == "__main__":
    unittest.main()

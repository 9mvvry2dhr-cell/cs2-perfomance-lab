import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.match_ai_report_repository import (
    MATCH_AI_REPORT_VERSION,
    MatchAIReportRepository,
)
from src.database.models import (
    Base,
    MatchModel,
    UserMatchModel,
    UserModel,
)


class MatchAIReportRepositoryTest(
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

        self.owner = "76561198055629469"
        self.match_id = "match-1"

        self.session.add(
            UserModel(
                steam_id=self.owner
            )
        )

        self.session.add(
            MatchModel(
                match_id=self.match_id,
                map_name="de_ancient",
                duration_seconds=0,
                rounds_played=20,
                score_ct=7,
                score_t=13,
                winner_side="T",
                is_valid=True,
                validation_error=None,
                analysis_version="v1",
                findings_version="v2",
            )
        )

        self.session.add(
            UserMatchModel(
                owner_steam_id=self.owner,
                match_id=self.match_id,
                player_position=0,
            )
        )

        self.session.commit()

        self.repository = (
            MatchAIReportRepository(
                self.session
            )
        )

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(
            self.engine
        )
        self.engine.dispose()

    def test_successful_generation_is_cached(self):
        cached = (
            self.repository
            .reserve_generation(
                owner_steam_id=self.owner,
                match_id=self.match_id,
            )
        )

        self.assertIsNone(
            cached
        )

        self.repository.commit_success(
            {
                "summary": "saved",
            }
        )

        self.assertEqual(
            self.repository
            .get_cached_response(
                owner_steam_id=self.owner,
                match_id=self.match_id,
            ),
            {
                "summary": "saved",
            },
        )

        model = self.session.get(
            UserMatchModel,
            (
                self.owner,
                self.match_id,
            ),
        )

        self.assertEqual(
            model.ai_explanation_version,
            MATCH_AI_REPORT_VERSION,
        )

        self.assertIsNotNone(
            model.ai_explanation_generated_at
        )

    def test_second_generation_returns_cache(self):
        self.repository.reserve_generation(
            owner_steam_id=self.owner,
            match_id=self.match_id,
        )

        self.repository.commit_success(
            {
                "summary": "first",
            }
        )

        cached = (
            self.repository
            .reserve_generation(
                owner_steam_id=self.owner,
                match_id=self.match_id,
            )
        )

        self.assertEqual(
            cached,
            {
                "summary": "first",
            },
        )

    def test_failure_does_not_create_cache(self):
        self.repository.reserve_generation(
            owner_steam_id=self.owner,
            match_id=self.match_id,
        )

        self.repository.cancel_generation()

        self.assertIsNone(
            self.repository
            .get_cached_response(
                owner_steam_id=self.owner,
                match_id=self.match_id,
            )
        )

    def test_other_user_cannot_read_cache(self):
        self.repository.reserve_generation(
            owner_steam_id=self.owner,
            match_id=self.match_id,
        )

        self.repository.commit_success(
            {
                "summary": "private",
            }
        )

        self.assertIsNone(
            self.repository
            .get_cached_response(
                owner_steam_id="other",
                match_id=self.match_id,
            )
        )


if __name__ == "__main__":
    unittest.main()

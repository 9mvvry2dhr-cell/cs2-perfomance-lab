import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.app import app
from src.api.dependencies import (
    get_analysis_repository,
    get_database_session,
)
from src.api.schemas import (
    MatchAnalysisResponse,
    PlayerHistorySummaryResponse,
    PlayerMatchHistoryResponse,
)
from src.domain.history import (
    PlayerMatchHistoryItem,
    build_player_history_summary,
)
from tests.unit.test_analysis_repository import make_analysis


class StubAnalysisRepository:
    def __init__(
        self,
        analysis=None,
        error=None,
        history=None,
        summary=None,
    ):
        self.analysis = analysis
        self.error = error
        self.history = (
            history
            if history is not None
            else []
        )
        self.summary = summary

    def get_analysis(
        self,
        match_id: str,
    ):
        if self.error is not None:
            raise self.error

        if (
            self.analysis is not None
            and self.analysis.match_id == match_id
        ):
            return self.analysis

        return None

    def get_player_match_history(
        self,
        steam_id: str,
        *,
        limit: int = 20,
    ):
        if self.error is not None:
            raise self.error

        return self.history[:limit]

    def get_player_history_summary(
        self,
        steam_id: str,
        *,
        limit: int = 10,
    ):
        if self.error is not None:
            raise self.error

        return self.summary


class StubSession:
    def execute(self, _):
        return None


class ApiTest(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_returns_ok(self):
        client = TestClient(app)

        response = client.get(
            "/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json(),
            {"status": "ok"},
        )

    def test_ready_returns_ready(self):
        app.dependency_overrides[
            get_database_session
        ] = lambda: StubSession()

        client = TestClient(app)

        response = client.get(
            "/ready"
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json(),
            {"status": "ready"},
        )

    def test_get_match_returns_analysis(self):
        expected = make_analysis()

        repository = StubAnalysisRepository(
            analysis=expected
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            f"/matches/{expected.match_id}"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected_json = (
            MatchAnalysisResponse
            .model_validate(expected)
            .model_dump(mode="json")
        )

        self.assertEqual(
            response.json(),
            expected_json,
        )

    def test_get_match_returns_404_when_missing(self):
        repository = StubAnalysisRepository()

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/matches/missing-match"
        )

        self.assertEqual(
            response.status_code,
            404,
        )
        self.assertEqual(
            response.json(),
            {
                "detail": "Match not found",
            },
        )

    def test_database_error_returns_503(self):
        repository = StubAnalysisRepository(
            error=SQLAlchemyError(
                "simulated database failure"
            )
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/matches/test-match"
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        self.assertEqual(
            response.json(),
            {
                "detail": "Database unavailable",
            },
        )


    def _history_item(self):
        analysis = make_analysis()

        player = analysis.players[0]

        return PlayerMatchHistoryItem(
            match_id=analysis.match_id,
            analyzed_at=datetime(
                2026,
                9,
                18,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            map_name=analysis.map_name,
            score_ct=analysis.score_ct,
            score_t=analysis.score_t,
            player_name=player.name,
            stats=player.stats,
            findings=player.findings,
        )


    def test_get_player_matches_returns_history(self):
        item = self._history_item()

        repository = StubAnalysisRepository(
            history=[
                item
            ]
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/players/76561198055629469/matches"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected = [
            (
                PlayerMatchHistoryResponse
                .model_validate(item)
                .model_dump(mode="json")
            )
        ]

        self.assertEqual(
            response.json(),
            expected,
        )


    def test_get_player_matches_returns_empty_for_unknown_player(self):
        repository = StubAnalysisRepository(
            history=[]
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/players/missing-player/matches"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json(),
            [],
        )


    def test_get_player_summary_returns_summary(self):
        item = self._history_item()

        summary = build_player_history_summary(
            "76561198055629469",
            [
                item
            ],
        )

        repository = StubAnalysisRepository(
            summary=summary
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/players/76561198055629469/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected = (
            PlayerHistorySummaryResponse
            .model_validate(summary)
            .model_dump(mode="json")
        )

        self.assertEqual(
            response.json(),
            expected,
        )


    def test_get_player_summary_returns_404_when_missing(self):
        repository = StubAnalysisRepository(
            summary=None
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/players/missing-player/summary"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Player history not found"
                ),
            },
        )


    def test_player_history_limit_is_validated(self):
        repository = StubAnalysisRepository()

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        for endpoint in (
            "matches",
            "summary",
        ):
            for limit in (
                0,
                101,
            ):
                with self.subTest(
                    endpoint=endpoint,
                    limit=limit,
                ):
                    response = client.get(
                        (
                            "/players/123/"
                            f"{endpoint}"
                            f"?limit={limit}"
                        )
                    )

                    self.assertEqual(
                        response.status_code,
                        422,
                    )


if __name__ == "__main__":
    unittest.main()

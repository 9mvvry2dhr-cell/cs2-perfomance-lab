import unittest

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.app import app
from src.api.dependencies import (
    get_analysis_repository,
    get_database_session,
)
from src.api.schemas import MatchAnalysisResponse
from tests.unit.test_analysis_repository import make_analysis


class StubAnalysisRepository:
    def __init__(
        self,
        analysis=None,
        error=None,
    ):
        self.analysis = analysis
        self.error = error

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


if __name__ == "__main__":
    unittest.main()

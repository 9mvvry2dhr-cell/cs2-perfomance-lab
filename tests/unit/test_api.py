import unittest

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import get_analysis_repository
from src.api.schemas import MatchAnalysisResponse
from tests.unit.test_analysis_repository import make_analysis


class StubAnalysisRepository:
    def __init__(self, analysis=None):
        self.analysis = analysis

    def get_analysis(self, match_id: str):
        if (
            self.analysis is not None
            and self.analysis.match_id == match_id
        ):
            return self.analysis

        return None


class ApiTest(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_returns_ok(self):
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json(),
            {"status": "ok"},
        )

    def test_get_match_returns_analysis(self):
        expected = make_analysis()

        repository = StubAnalysisRepository(
            expected
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


if __name__ == "__main__":
    unittest.main()

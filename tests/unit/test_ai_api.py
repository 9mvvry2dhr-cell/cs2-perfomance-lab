import unittest

from fastapi.testclient import TestClient

from src.ai.client import (
    AIProviderError,
    AIResponseValidationError,
)
from src.ai.models import (
    AIExplanationItem,
    AIUsage,
    MatchAIExplanation,
    MatchAIResponse,
)
from src.api.app import app
from src.api.dependencies import (
    get_analysis_repository,
    get_current_user,
    get_match_ai_explainer,
)
from src.domain.identity import CurrentUser
from tests.unit.test_analysis_repository import make_analysis


class StubRepository:
    def __init__(
        self,
        analysis=None,
        user_match_position=0,
    ):
        self.analysis = analysis
        self.user_match_position = (
            user_match_position
        )
        self.position_requests = []

    def get_user_match_position(
        self,
        *,
        owner_steam_id,
        match_id,
    ):
        self.position_requests.append(
            (
                owner_steam_id,
                match_id,
            )
        )

        return self.user_match_position

    def get_analysis(self, match_id):
        if (
            self.analysis is not None
            and self.analysis.match_id == match_id
        ):
            return self.analysis

        return None


class StubExplainer:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.payloads = []

    def explain_with_usage(self, payload):
        self.payloads.append(payload)

        if self.error is not None:
            raise self.error

        return MatchAIResponse(
            **self.result.model_dump(),
            usage=AIUsage(
                input_tokens=3000,
                cached_input_tokens=0,
                output_tokens=800,
                reasoning_tokens=250,
                total_tokens=3800,
            ),
        )


def make_explanation():
    return MatchAIExplanation(
        summary="T-сторона заметно слабее по подтверждённым показателям.",
        strengths=[],
        weaknesses=[
            AIExplanationItem(
                title="Разрыв по сторонам",
                text="На T ниже ADR и KAST.",
                evidence_codes=[
                    "SIDE_PERFORMANCE_GAP"
                ],
            )
        ],
        focus=[
            AIExplanationItem(
                title="Разобрать T-раунды",
                text="Проверь повторяющиеся эпизоды на T.",
                evidence_codes=[
                    "SIDE_PERFORMANCE_GAP"
                ],
            )
        ],
        caveat="Матчевые данные не доказывают конкретную причину разрыва.",
    )


class MatchAIEndpointTest(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[
            get_current_user
        ] = lambda: CurrentUser(
            steam_id="76561198055629469"
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_returns_grounded_explanation_for_owned_match(self):
        analysis = make_analysis()
        explainer = StubExplainer(
            result=make_explanation()
        )

        repository = StubRepository(
            analysis
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        app.dependency_overrides[
            get_match_ai_explainer
        ] = lambda: explainer

        response = TestClient(app).post(
            f"/matches/{analysis.match_id}/ai-explanation"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            repository.position_requests,
            [
                (
                    "76561198055629469",
                    analysis.match_id,
                )
            ],
        )

        self.assertEqual(
            response.json()["weaknesses"][0]["evidence_codes"],
            ["SIDE_PERFORMANCE_GAP"],
        )

        self.assertEqual(
            response.json()["usage"]["input_tokens"],
            3000,
        )

        self.assertEqual(
            response.json()["usage"]["reasoning_tokens"],
            250,
        )

        self.assertEqual(
            len(explainer.payloads),
            1,
        )

        encoded = str(
            explainer.payloads[0]
        )

        self.assertNotIn(
            "76561198055629469",
            encoded,
        )

    def test_hides_match_without_user_match_link(self):
        analysis = make_analysis()

        repository = StubRepository(
            analysis,
            user_match_position=None,
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        app.dependency_overrides[
            get_match_ai_explainer
        ] = lambda: StubExplainer(
            result=make_explanation()
        )

        response = TestClient(app).post(
            f"/matches/{analysis.match_id}/ai-explanation"
        )

        self.assertEqual(
            response.status_code,
            404,
        )


    def test_provider_failure_returns_502(self):
        analysis = make_analysis()

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: StubRepository(
            analysis
        )

        app.dependency_overrides[
            get_match_ai_explainer
        ] = lambda: StubExplainer(
            error=AIProviderError(
                "simulated"
            )
        )

        response = TestClient(app).post(
            f"/matches/{analysis.match_id}/ai-explanation"
        )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": "AI provider request failed",
            },
        )

    def test_evidence_validation_failure_returns_502(self):
        analysis = make_analysis()

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: StubRepository(
            analysis
        )

        app.dependency_overrides[
            get_match_ai_explainer
        ] = lambda: StubExplainer(
            error=AIResponseValidationError(
                "simulated"
            )
        )

        response = TestClient(app).post(
            f"/matches/{analysis.match_id}/ai-explanation"
        )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": "AI response failed evidence validation",
            },
        )


if __name__ == "__main__":
    unittest.main()

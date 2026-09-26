import unittest
from types import SimpleNamespace

from src.ai.client import (
    AIResponseValidationError,
    OpenAIPlayerExplainer,
    validate_player_explanation_grounding,
)
from src.ai.models import (
    AIExplanationItem,
    PlayerAIExplanation,
)


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            output_parsed=self.parsed,
            usage=None,
        )


class FakeClient:
    def __init__(self, parsed):
        self.responses = FakeResponses(
            parsed
        )


def make_payload():
    return {
        "source_scope": {
            "matches_included": 10,
            "rounds_included": 220,
        },
        "evidence_catalog": [
            {
                "code": "overall:profile",
                "kind": "context",
                "data": {},
            },
            {
                "code": "finding:GOOD_OPENING",
                "kind": "strength",
                "data": {},
            },
            {
                "code": "finding:LOW_TRADES",
                "kind": "weakness",
                "data": {},
            },
            {
                "code": "trend:kd",
                "kind": "trend",
                "data": {},
            },
            {
                "code": "map:de_mirage",
                "kind": "map",
                "data": {},
            },
        ],
    }


def make_explanation():
    return PlayerAIExplanation(
        summary="По десяти матчам уже виден рабочий профиль игрока.",
        profile=[
            AIExplanationItem(
                title="Активный первый контакт",
                text="Профиль строится вокруг ранних дуэлей.",
                evidence_codes=[
                    "overall:profile",
                    "finding:GOOD_OPENING",
                ],
            )
        ],
        strengths=[
            AIExplanationItem(
                title="Opening",
                text="Положительный сигнал повторяется.",
                evidence_codes=[
                    "finding:GOOD_OPENING",
                ],
            )
        ],
        weaknesses=[
            AIExplanationItem(
                title="Размены",
                text="Слабый сигнал повторяется.",
                evidence_codes=[
                    "finding:LOW_TRADES",
                ],
            )
        ],
        trends=[
            AIExplanationItem(
                title="K/D",
                text="Последнее окно ниже предыдущего.",
                evidence_codes=[
                    "trend:kd",
                ],
            )
        ],
        maps=[
            AIExplanationItem(
                title="Mirage",
                text="По карте есть отдельный контекст.",
                evidence_codes=[
                    "map:de_mirage",
                ],
            )
        ],
        focus=[
            AIExplanationItem(
                title="Следующие матчи",
                text="Проверь реализацию доступных разменов.",
                evidence_codes=[
                    "finding:LOW_TRADES",
                ],
            )
        ],
        caveat="Метрики не доказывают скрытую игровую причину.",
    )


class PlayerAIExplainerTest(unittest.TestCase):
    def test_uses_player_structured_model(self):
        explanation = make_explanation()
        client = FakeClient(
            explanation
        )

        explainer = OpenAIPlayerExplainer(
            client=client,
            model="test-model",
        )

        actual = explainer.explain(
            make_payload()
        )

        self.assertEqual(
            actual,
            explanation,
        )

        call = client.responses.calls[0]

        self.assertIs(
            call["text_format"],
            PlayerAIExplanation,
        )

        self.assertEqual(
            call["model"],
            "test-model",
        )

    def test_unknown_evidence_is_rejected(self):
        bad = make_explanation().model_copy(
            update={
                "focus": [
                    AIExplanationItem(
                        title="Unknown",
                        text="Unknown",
                        evidence_codes=[
                            "missing:evidence",
                        ],
                    )
                ]
            }
        )

        with self.assertRaises(
            AIResponseValidationError
        ):
            validate_player_explanation_grounding(
                bad,
                make_payload(),
            )

    def test_strength_requires_strength_evidence(self):
        bad = make_explanation().model_copy(
            update={
                "strengths": [
                    AIExplanationItem(
                        title="Wrong",
                        text="Wrong",
                        evidence_codes=[
                            "trend:kd",
                        ],
                    )
                ]
            }
        )

        with self.assertRaises(
            AIResponseValidationError
        ):
            validate_player_explanation_grounding(
                bad,
                make_payload(),
            )


if __name__ == "__main__":
    unittest.main()

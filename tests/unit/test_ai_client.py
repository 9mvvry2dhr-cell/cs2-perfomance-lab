import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.ai.client import (
    AIConfigurationError,
    AIResponseValidationError,
    DEFAULT_OPENAI_MODEL,
    OpenAIMatchExplainer,
    validate_explanation_grounding,
)
from src.ai.models import (
    AIExplanationItem,
    MatchAIExplanation,
)
from src.ai.payload import build_match_ai_payload
from tests.unit.test_analysis_repository import make_analysis


class FakeResponses:
    def __init__(
        self,
        parsed,
        usage=None,
    ):
        self.parsed = parsed
        self.usage = usage
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            output_parsed=self.parsed,
            usage=self.usage,
        )


class FakeClient:
    def __init__(
        self,
        parsed,
        usage=None,
    ):
        self.responses = FakeResponses(
            parsed,
            usage=usage,
        )


class OpenAIMatchExplainerTest(unittest.TestCase):

    def _payload(self):
        return build_match_ai_payload(
            make_analysis(),
            steam_id="76561198055629469",
        )


    def _valid_explanation(self):
        return MatchAIExplanation(
            summary="На T сторона заметно слабее по подтверждённым показателям.",
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
                    text="Проверь повторяющиеся эпизоды на T, не считая причину заранее доказанной.",
                    evidence_codes=[
                        "SIDE_PERFORMANCE_GAP"
                    ],
                )
            ],
            caveat="Эти данные не доказывают конкретную игровую причину разрыва.",
        )


    def test_explain_uses_responses_parse_and_structured_model(self):
        explanation = self._valid_explanation()
        client = FakeClient(
            explanation
        )

        explainer = OpenAIMatchExplainer(
            client=client,
            model="test-model",
        )

        actual = explainer.explain(
            self._payload()
        )

        self.assertEqual(
            actual,
            explanation,
        )

        self.assertEqual(
            len(client.responses.calls),
            1,
        )

        call = client.responses.calls[0]

        self.assertEqual(
            call["model"],
            "test-model",
        )

        self.assertIs(
            call["store"],
            False,
        )

        self.assertIs(
            call["text_format"],
            MatchAIExplanation,
        )

        self.assertEqual(
            call["input"][0]["role"],
            "system",
        )

        self.assertEqual(
            call["input"][1]["role"],
            "user",
        )


    def test_unknown_evidence_code_is_rejected(self):
        explanation = self._valid_explanation()

        bad = explanation.model_copy(
            update={
                "weaknesses": [
                    AIExplanationItem(
                        title="Invented",
                        text="Invented",
                        evidence_codes=[
                            "NOT_IN_PAYLOAD"
                        ],
                    )
                ]
            }
        )

        with self.assertRaises(
            AIResponseValidationError
        ):
            validate_explanation_grounding(
                bad,
                self._payload(),
            )


    def test_strength_cannot_use_weakness_finding(self):
        explanation = self._valid_explanation()

        bad = explanation.model_copy(
            update={
                "strengths": [
                    AIExplanationItem(
                        title="Wrong kind",
                        text="Wrong kind",
                        evidence_codes=[
                            "SIDE_PERFORMANCE_GAP"
                        ],
                    )
                ],
                "weaknesses": [],
                "focus": [],
            }
        )

        with self.assertRaises(
            AIResponseValidationError
        ):
            validate_explanation_grounding(
                bad,
                self._payload(),
            )


    def test_focus_may_use_verified_strength(self):
        payload = self._payload()

        payload["verified_findings"].append(
            {
                "code": "TEST_STRENGTH",
                "category": "test",
                "kind": "strength",
                "severity": "low",
                "side": "MATCH",
                "evidence": {},
            }
        )

        explanation = self._valid_explanation().model_copy(
            update={
                "focus": [
                    AIExplanationItem(
                        title="Preserve repeatable strength",
                        text="Review when this strength appeared and whether it repeats.",
                        evidence_codes=[
                            "TEST_STRENGTH"
                        ],
                    )
                ]
            }
        )

        validate_explanation_grounding(
            explanation,
            payload,
        )


    def test_empty_evidence_codes_are_rejected(self):
        bad = self._valid_explanation().model_copy(
            update={
                "weaknesses": [
                    AIExplanationItem(
                        title="Ungrounded",
                        text="Ungrounded",
                        evidence_codes=[],
                    )
                ]
            }
        )

        with self.assertRaises(
            AIResponseValidationError
        ):
            validate_explanation_grounding(
                bad,
                self._payload(),
            )


    def test_focus_is_required_when_findings_exist(self):
        bad = self._valid_explanation().model_copy(
            update={
                "focus": [],
            }
        )

        with self.assertRaises(
            AIResponseValidationError
        ):
            validate_explanation_grounding(
                bad,
                self._payload(),
            )


    def test_explain_with_usage_reports_response_usage(self):
        explanation = self._valid_explanation()

        usage = SimpleNamespace(
            input_tokens=3120,
            input_tokens_details=SimpleNamespace(
                cached_tokens=120,
            ),
            output_tokens=910,
            output_tokens_details=SimpleNamespace(
                reasoning_tokens=310,
            ),
            total_tokens=4030,
        )

        client = FakeClient(
            explanation,
            usage=usage,
        )

        explainer = OpenAIMatchExplainer(
            client=client,
            model="test-model",
        )

        result = explainer.explain_with_usage(
            self._payload()
        )

        self.assertEqual(
            result.usage.input_tokens,
            3120,
        )

        self.assertEqual(
            result.usage.cached_input_tokens,
            120,
        )

        self.assertEqual(
            result.usage.output_tokens,
            910,
        )

        self.assertEqual(
            result.usage.reasoning_tokens,
            310,
        )

        self.assertEqual(
            result.usage.total_tokens,
            4030,
        )


    def test_missing_api_key_is_rejected_without_network_client(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
            },
            clear=False,
        ):
            with self.assertRaises(
                AIConfigurationError
            ):
                OpenAIMatchExplainer()


    def test_default_model_is_gpt_5_6(self):
        client = FakeClient(
            self._valid_explanation()
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_MODEL": "",
            },
            clear=False,
        ):
            explainer = OpenAIMatchExplainer(
                client=client,
            )

        self.assertEqual(
            explainer.model,
            DEFAULT_OPENAI_MODEL,
        )


if __name__ == "__main__":
    unittest.main()

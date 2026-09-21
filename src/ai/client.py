from __future__ import annotations

import os
from typing import Any, Mapping

from openai import OpenAI

from src.ai.models import MatchAIExplanation
from src.ai.prompt import build_match_ai_prompt


DEFAULT_OPENAI_MODEL = "gpt-5.6"


class AIConfigurationError(RuntimeError):
    pass


class AIResponseValidationError(RuntimeError):
    pass


class AIProviderError(RuntimeError):
    pass


def _finding_kinds(
    payload: Mapping[str, Any],
) -> dict[str, str]:
    result: dict[str, str] = {}

    for finding in payload.get(
        "verified_findings",
        [],
    ):
        code = str(
            finding.get(
                "code",
                "",
            )
        )

        kind = str(
            finding.get(
                "kind",
                "",
            )
        )

        if code:
            result[code] = kind

    return result


def validate_explanation_grounding(
    explanation: MatchAIExplanation,
    payload: Mapping[str, Any],
) -> None:
    """
    Reject model output that escapes the deterministic evidence contract.

    Structured output guarantees shape, but the allowed evidence codes are
    dynamic per match, so we verify those references after generation.
    """

    finding_kinds = _finding_kinds(
        payload
    )

    def validate_items(
        section: str,
        items,
        *,
        allowed_kind: str | None,
    ) -> None:
        for item in items:
            if not item.evidence_codes:
                raise AIResponseValidationError(
                    f"{section} item has no evidence codes"
                )

            for code in item.evidence_codes:
                kind = finding_kinds.get(
                    code
                )

                if kind is None:
                    raise AIResponseValidationError(
                        f"{section} references unknown evidence code: {code}"
                    )

                if (
                    allowed_kind is not None
                    and kind != allowed_kind
                ):
                    raise AIResponseValidationError(
                        f"{section} references {kind} finding: {code}"
                    )

    validate_items(
        "strengths",
        explanation.strengths,
        allowed_kind="strength",
    )

    validate_items(
        "weaknesses",
        explanation.weaknesses,
        allowed_kind="weakness",
    )

    validate_items(
        "focus",
        explanation.focus,
        allowed_kind="weakness",
    )


class OpenAIMatchExplainer:
    def __init__(
        self,
        *,
        client=None,
        model: str | None = None,
    ):
        self.model = (
            model
            or os.getenv(
                "OPENAI_MODEL",
                DEFAULT_OPENAI_MODEL,
            ).strip()
            or DEFAULT_OPENAI_MODEL
        )

        if client is not None:
            self.client = client
            return

        api_key = os.getenv(
            "OPENAI_API_KEY",
            "",
        ).strip()

        if not api_key:
            raise AIConfigurationError(
                "OPENAI_API_KEY is not configured"
            )

        self.client = OpenAI(
            api_key=api_key,
        )

    def explain(
        self,
        payload: Mapping[str, Any],
    ) -> MatchAIExplanation:
        prompt = build_match_ai_prompt(
            payload
        )

        try:
            response = (
                self.client.responses.parse(
                    model=self.model,
                    input=[
                        {
                            "role": "system",
                            "content": prompt.instructions,
                        },
                        {
                            "role": "user",
                            "content": prompt.input_text,
                        },
                    ],
                    text_format=MatchAIExplanation,
                )
            )
        except Exception as exc:
            raise AIProviderError(
                "OpenAI request failed"
            ) from exc

        explanation = (
            response.output_parsed
        )

        if explanation is None:
            raise AIResponseValidationError(
                "OpenAI response did not contain parsed output"
            )

        validate_explanation_grounding(
            explanation,
            payload,
        )

        return explanation

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AIExplanationItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    title: str = Field(
        min_length=1,
        max_length=120,
    )
    text: str = Field(
        min_length=1,
        max_length=1200,
    )
    evidence_codes: list[str]


class MatchAIExplanation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    summary: str = Field(
        min_length=1,
        max_length=2000,
    )
    strengths: list[AIExplanationItem]
    weaknesses: list[AIExplanationItem]
    focus: list[AIExplanationItem]
    caveat: str = Field(
        min_length=1,
        max_length=1200,
    )

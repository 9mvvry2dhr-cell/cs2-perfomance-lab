from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.domain.analysis import MatchAnalysis


AI_PAYLOAD_VERSION = "v1"


class AIPlayerNotFoundError(ValueError):
    pass


def _finding_payload(finding) -> dict[str, Any]:
    return {
        "code": finding.code,
        "category": finding.category,
        "kind": finding.kind,
        "severity": finding.severity,
        "side": finding.side,
        "evidence": {
            key: float(value)
            for key, value in finding.evidence.items()
        },
    }


def build_match_ai_payload(
    analysis: MatchAnalysis,
    *,
    steam_id: str,
) -> dict[str, Any]:
    """
    Build the provider-agnostic AI input contract for one player/match.

    Important:
    - this function does not calculate gameplay metrics;
    - it only serializes already verified analysis data;
    - SteamID is used only to select the player and is not sent in payload;
    - deterministic findings and their evidence are passed verbatim;
    - no free-form diagnosis is generated here.
    """

    player = next(
        (
            item
            for item in analysis.players
            if item.steam_id == steam_id
        ),
        None,
    )

    if player is None:
        raise AIPlayerNotFoundError(
            "Player is not present in match analysis"
        )

    overall = asdict(
        player.stats
    )

    sides = {
        side: asdict(stats)
        for side, stats in player.sides.items()
        if side in {"CT", "T"}
    }

    return {
        "schema_version": AI_PAYLOAD_VERSION,
        "match": {
            "map_name": analysis.map_name,
            "rounds_played": analysis.rounds_played,
            "score_ct": analysis.score_ct,
            "score_t": analysis.score_t,
        },
        "verified_metrics": {
            "overall": overall,
            "sides": sides,
        },
        "verified_findings": [
            _finding_payload(finding)
            for finding in player.findings
        ],
        "evidence_contract": {
            "metrics_are_precomputed": True,
            "findings_are_deterministic": True,
            "model_must_not_recalculate_metrics": True,
            "model_must_not_invent_unobserved_causes": True,
            "model_must_distinguish_fact_from_possible_interpretation": True,
        },
    }

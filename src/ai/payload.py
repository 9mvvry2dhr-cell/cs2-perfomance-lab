from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.domain.analysis import MatchAnalysis
from src.domain.history import (
    PlayerHistorySummary,
    PlayerMatchHistoryItem,
)


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
    - score_ct/score_t are side round totals, not the player's team result;
    - player_result stays unknown until the parser persists team identity;
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
            "score_semantics": "ct_t_side_round_totals",
            "player_result": (
                analysis.player_results.get(
                    steam_id,
                    "unknown",
                )
            ),
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



PLAYER_AI_PAYLOAD_VERSION = "player-v1"


_TREND_CONFIG = {
    "kd": {
        "label": "K/D",
        "neutral_delta": 0.05,
    },
    "adr": {
        "label": "ADR",
        "neutral_delta": 2.4,
    },
    "kast_pct": {
        "label": "KAST",
        "neutral_delta": 1.6,
    },
    "entry_balance": {
        "label": "Entry +/-",
        "neutral_delta": 0.3,
    },
    "utility_per_round": {
        "label": "Utility / round",
        "neutral_delta": 0.5,
    },
    "survival_pct": {
        "label": "Survival",
        "neutral_delta": 1.6,
    },
}


def _safe_rate(
    numerator: float,
    denominator: float,
    *,
    digits: int = 2,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        numerator / denominator,
        digits,
    )


def _safe_pct(
    numerator: float,
    denominator: float,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        numerator / denominator * 100,
        1,
    )


def _result_counts(
    matches: list[PlayerMatchHistoryItem],
) -> dict[str, int]:
    counts = {
        "win": 0,
        "loss": 0,
        "draw": 0,
        "unknown": 0,
    }

    for item in matches:
        result = (
            item.player_result
            if item.player_result in counts
            else "unknown"
        )

        counts[result] += 1

    return counts


def _aggregate_items(
    matches: list[PlayerMatchHistoryItem],
) -> dict[str, Any]:
    rounds = sum(
        item.stats.rounds_played
        for item in matches
    )
    kills = sum(
        item.stats.kills
        for item in matches
    )
    deaths = sum(
        item.stats.deaths
        for item in matches
    )
    damage = sum(
        float(item.stats.damage)
        for item in matches
    )
    kast_rounds = sum(
        item.stats.kast_rounds
        for item in matches
    )
    survived_rounds = sum(
        item.stats.survived_rounds
        for item in matches
    )
    entry_kills = sum(
        item.stats.entry_kills
        for item in matches
    )
    entry_deaths = sum(
        item.stats.entry_deaths
        for item in matches
    )
    utility_damage = sum(
        float(item.stats.he_damage)
        + float(item.stats.inferno_damage)
        for item in matches
    )

    clutch_known = [
        item
        for item in matches
        if item.stats.clutch_attempts is not None
    ]
    clutch_attempts = sum(
        int(item.stats.clutch_attempts or 0)
        for item in clutch_known
    )
    clutch_wins = sum(
        item.stats.clutches_won
        for item in clutch_known
    )

    trade_known = [
        item
        for item in matches
        if item.stats.trade_opportunities is not None
    ]
    trade_opportunities = sum(
        int(item.stats.trade_opportunities or 0)
        for item in trade_known
    )
    trade_kills = sum(
        item.stats.trade_kills
        for item in trade_known
    )

    return {
        "matches": len(matches),
        "rounds_played": rounds,
        "kills": kills,
        "deaths": deaths,
        "kd": _safe_rate(
            kills,
            deaths,
        ),
        "adr": _safe_rate(
            damage,
            rounds,
            digits=1,
        ),
        "kast_pct": _safe_pct(
            kast_rounds,
            rounds,
        ),
        "survival_pct": _safe_pct(
            survived_rounds,
            rounds,
        ),
        "entry_kills": entry_kills,
        "entry_deaths": entry_deaths,
        "entry_balance": (
            entry_kills
            - entry_deaths
        ),
        "utility_damage": round(
            utility_damage,
            1,
        ),
        "utility_per_round": _safe_rate(
            utility_damage,
            rounds,
            digits=1,
        ),
        "clutch_known_matches": len(
            clutch_known
        ),
        "clutch_wins": clutch_wins,
        "clutch_attempts": (
            clutch_attempts
            if clutch_known
            else None
        ),
        "clutch_conversion_pct": (
            _safe_pct(
                clutch_wins,
                clutch_attempts,
            )
            if clutch_attempts > 0
            else None
        ),
        "trade_known_matches": len(
            trade_known
        ),
        "trade_kills": trade_kills,
        "trade_opportunities": (
            trade_opportunities
            if trade_known
            else None
        ),
        "trade_conversion_pct": (
            _safe_pct(
                trade_kills,
                trade_opportunities,
            )
            if trade_opportunities > 0
            else None
        ),
        "results": _result_counts(
            matches
        ),
    }


def _aggregate_side(
    matches: list[PlayerMatchHistoryItem],
    side_name: str,
) -> dict[str, Any]:
    sides = [
        item.sides[side_name]
        for item in matches
        if side_name in item.sides
    ]

    rounds = sum(
        item.rounds_played
        for item in sides
    )
    kills = sum(
        item.kills
        for item in sides
    )
    deaths = sum(
        item.deaths
        for item in sides
    )
    damage = sum(
        float(item.damage)
        for item in sides
    )
    kast_rounds = sum(
        item.kast_rounds
        for item in sides
    )
    survived_rounds = sum(
        item.survived_rounds
        for item in sides
    )
    entry_kills = sum(
        item.entry_kills
        for item in sides
    )
    entry_deaths = sum(
        item.entry_deaths
        for item in sides
    )

    return {
        "rounds_played": rounds,
        "kd": _safe_rate(
            kills,
            deaths,
        ),
        "adr": _safe_rate(
            damage,
            rounds,
            digits=1,
        ),
        "kast_pct": _safe_pct(
            kast_rounds,
            rounds,
        ),
        "survival_pct": _safe_pct(
            survived_rounds,
            rounds,
        ),
        "entry_kills": entry_kills,
        "entry_deaths": entry_deaths,
        "entry_balance": (
            entry_kills
            - entry_deaths
        ),
    }


def _trend_window(
    count: int,
) -> int:
    if count >= 10:
        return 5

    if count >= 6:
        return 3

    if count >= 4:
        return 2

    return 0


def _trend_value(
    item: PlayerMatchHistoryItem,
    key: str,
) -> float:
    stats = item.stats

    if key == "kd":
        return float(stats.kd)

    if key == "adr":
        return float(stats.adr)

    if key == "kast_pct":
        return float(stats.kast_pct)

    if key == "entry_balance":
        return float(
            stats.entry_kills
            - stats.entry_deaths
        )

    if key == "utility_per_round":
        utility = (
            float(stats.he_damage)
            + float(stats.inferno_damage)
        )

        return _safe_rate(
            utility,
            stats.rounds_played,
            digits=2,
        )

    if key == "survival_pct":
        return float(
            stats.survival_pct
        )

    raise ValueError(
        f"Unsupported trend metric: {key}"
    )


def _mean(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def _build_trends(
    matches: list[PlayerMatchHistoryItem],
) -> list[dict[str, Any]]:
    chronological = list(
        reversed(matches)
    )

    window = _trend_window(
        len(chronological)
    )

    if not window:
        return []

    result = []

    for key, config in (
        _TREND_CONFIG.items()
    ):
        values = [
            _trend_value(
                item,
                key,
            )
            for item in chronological
        ]

        previous = values[
            -window * 2:
            -window
        ]
        recent = values[
            -window:
        ]

        if (
            len(previous) != window
            or len(recent) != window
        ):
            continue

        previous_average = _mean(
            previous
        )
        recent_average = _mean(
            recent
        )
        delta = (
            recent_average
            - previous_average
        )

        if abs(delta) < float(
            config["neutral_delta"]
        ):
            direction = "flat"
        elif delta > 0:
            direction = "up"
        else:
            direction = "down"

        relative_delta_pct = (
            round(
                delta
                / abs(previous_average)
                * 100,
                1,
            )
            if abs(previous_average) > 0.0001
            else None
        )

        result.append(
            {
                "evidence_code": (
                    "trend:"
                    + key
                ),
                "metric": key,
                "label": config["label"],
                "window_matches": window,
                "previous_average": round(
                    previous_average,
                    2,
                ),
                "recent_average": round(
                    recent_average,
                    2,
                ),
                "delta": round(
                    delta,
                    2,
                ),
                "relative_delta_pct": (
                    relative_delta_pct
                ),
                "direction": direction,
            }
        )

    return result


def _build_map_summaries(
    matches: list[PlayerMatchHistoryItem],
) -> list[dict[str, Any]]:
    grouped: dict[
        str,
        list[PlayerMatchHistoryItem],
    ] = {}

    for item in matches:
        grouped.setdefault(
            item.map_name,
            [],
        ).append(
            item
        )

    result = []

    for map_name, items in grouped.items():
        metrics = _aggregate_items(
            items
        )

        result.append(
            {
                "evidence_code": (
                    "map:"
                    + map_name
                ),
                "map_name": map_name,
                **metrics,
            }
        )

    result.sort(
        key=lambda item: (
            -int(item["matches"]),
            str(item["map_name"]),
        )
    )

    return result


def _finding_samples(
    matches: list[PlayerMatchHistoryItem],
    code: str,
) -> list[dict[str, Any]]:
    samples = []

    for item in matches:
        for finding in item.findings:
            if finding.code != code:
                continue

            samples.append(
                {
                    "map_name": item.map_name,
                    "side": finding.side,
                    "severity": finding.severity,
                    "evidence": {
                        key: float(value)
                        for key, value
                        in finding.evidence.items()
                    },
                }
            )

            break

        if len(samples) >= 3:
            break

    return samples


def build_player_ai_payload(
    summary: PlayerHistorySummary,
    matches: list[PlayerMatchHistoryItem],
) -> dict[str, Any]:
    """
    Build a compact longitudinal AI payload from already persisted analytics.

    Identity values are intentionally excluded. The model receives only
    aggregated metrics, deterministic recurring findings and compact
    per-map/trend context derived by the backend.
    """
    if not matches:
        raise ValueError(
            "Player history must not be empty"
        )

    recurring_findings = [
        {
            "evidence_code": (
                "finding:"
                + item.code
            ),
            "code": item.code,
            "category": item.category,
            "kind": item.kind,
            "matches": item.matches,
            "match_rate_pct": (
                item.match_rate_pct
            ),
            "sample_evidence": (
                _finding_samples(
                    matches,
                    item.code,
                )
            ),
        }
        for item
        in summary.finding_frequency
        if item.matches >= 2
    ]

    trends = _build_trends(
        matches
    )

    maps = _build_map_summaries(
        matches
    )

    sides = {
        side: _aggregate_side(
            matches,
            side,
        )
        for side in (
            "CT",
            "T",
        )
    }

    overall = _aggregate_items(
        matches
    )

    evidence_catalog = [
        {
            "code": "overall:profile",
            "kind": "context",
            "data": overall,
        }
    ]

    if (
        sides["CT"]["rounds_played"] > 0
        and sides["T"]["rounds_played"] > 0
    ):
        evidence_catalog.append(
            {
                "code": "side:ct_vs_t",
                "kind": "context",
                "data": sides,
            }
        )

    evidence_catalog.extend(
        {
            "code": item["evidence_code"],
            "kind": item["kind"],
            "data": item,
        }
        for item in recurring_findings
    )

    evidence_catalog.extend(
        {
            "code": item["evidence_code"],
            "kind": "trend",
            "data": item,
        }
        for item in trends
    )

    evidence_catalog.extend(
        {
            "code": item["evidence_code"],
            "kind": "map",
            "data": item,
        }
        for item in maps
    )

    recent_matches = [
        {
            "map_name": item.map_name,
            "player_result": (
                item.player_result
            ),
            "rounds_played": (
                item.stats.rounds_played
            ),
            "kd": item.stats.kd,
            "adr": item.stats.adr,
            "kast_pct": (
                item.stats.kast_pct
            ),
            "survival_pct": (
                item.stats.survival_pct
            ),
            "entry_balance": (
                item.stats.entry_kills
                - item.stats.entry_deaths
            ),
        }
        for item in matches[:10]
    ]

    return {
        "schema_version": (
            PLAYER_AI_PAYLOAD_VERSION
        ),
        "source_scope": {
            "matches_included": len(
                matches
            ),
            "rounds_included": (
                summary.stats.rounds_played
            ),
            "history_limit": 100,
        },
        "verified_profile": {
            "overall": overall,
            "sides": sides,
            "recurring_findings": (
                recurring_findings
            ),
            "trends": trends,
            "maps": maps,
            "recent_matches": (
                recent_matches
            ),
        },
        "evidence_catalog": (
            evidence_catalog
        ),
        "evidence_contract": {
            "metrics_are_precomputed": True,
            "recurring_findings_are_deterministic": True,
            "trends_are_backend_comparisons": True,
            "map_metrics_are_backend_aggregates": True,
            "model_must_not_recalculate_metrics": True,
            "model_must_not_invent_unobserved_causes": True,
        },
    }

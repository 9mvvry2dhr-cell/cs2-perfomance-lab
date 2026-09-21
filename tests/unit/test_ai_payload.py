import json
import unittest

from dataclasses import replace

from src.ai.payload import (
    AI_PAYLOAD_VERSION,
    AIPlayerNotFoundError,
    build_match_ai_payload,
)
from tests.unit.test_analysis_repository import make_analysis


class MatchAIPayloadTest(unittest.TestCase):

    def test_builds_verified_provider_agnostic_payload(self):
        analysis = make_analysis()

        payload = build_match_ai_payload(
            analysis,
            steam_id="76561198055629469",
        )

        self.assertEqual(
            payload["schema_version"],
            AI_PAYLOAD_VERSION,
        )

        self.assertEqual(
            payload["match"],
            {
                "map_name": "de_mirage",
                "rounds_played": 24,
                "score_ct": 13,
                "score_t": 11,
                "score_semantics": "ct_t_side_round_totals",
                "player_result": "unknown",
            },
        )

        overall = payload[
            "verified_metrics"
        ][
            "overall"
        ]

        self.assertEqual(
            overall["kills"],
            24,
        )

        self.assertEqual(
            overall["deaths"],
            16,
        )

        self.assertEqual(
            overall["adr"],
            93.4,
        )

        self.assertEqual(
            overall["kast_pct"],
            66.7,
        )

        sides = payload[
            "verified_metrics"
        ][
            "sides"
        ]

        self.assertEqual(
            set(sides),
            {"CT", "T"},
        )

        self.assertEqual(
            sides["CT"]["adr"],
            123.5,
        )

        self.assertEqual(
            sides["T"]["adr"],
            63.3,
        )

        findings = payload[
            "verified_findings"
        ]

        self.assertEqual(
            len(findings),
            1,
        )

        self.assertEqual(
            findings[0]["code"],
            "SIDE_PERFORMANCE_GAP",
        )

        self.assertEqual(
            findings[0]["side"],
            "T",
        )

        self.assertEqual(
            findings[0]["evidence"]["adr_gap"],
            60.2,
        )


    def test_payload_does_not_expose_steam_id_or_match_id(self):
        analysis = make_analysis()

        payload = build_match_ai_payload(
            analysis,
            steam_id="76561198055629469",
        )

        encoded = json.dumps(
            payload,
            sort_keys=True,
        )

        self.assertNotIn(
            "76561198055629469",
            encoded,
        )

        self.assertNotIn(
            analysis.match_id,
            encoded,
        )


    def test_payload_is_json_serializable(self):
        payload = build_match_ai_payload(
            make_analysis(),
            steam_id="76561198055629469",
        )

        json.dumps(payload)


    def test_evidence_contract_forbids_metric_recalculation_and_invention(self):
        payload = build_match_ai_payload(
            make_analysis(),
            steam_id="76561198055629469",
        )

        contract = payload[
            "evidence_contract"
        ]

        self.assertTrue(
            contract["metrics_are_precomputed"]
        )

        self.assertTrue(
            contract["findings_are_deterministic"]
        )

        self.assertTrue(
            contract["model_must_not_recalculate_metrics"]
        )

        self.assertTrue(
            contract["model_must_not_invent_unobserved_causes"]
        )

        self.assertTrue(
            contract[
                "model_must_distinguish_fact_from_possible_interpretation"
            ]
        )


    def test_missing_player_is_rejected(self):
        analysis = make_analysis()

        with self.assertRaises(
            AIPlayerNotFoundError
        ):
            build_match_ai_payload(
                analysis,
                steam_id="missing-player",
            )


    def test_payload_selects_only_requested_player(self):
        analysis = make_analysis()

        first = analysis.players[0]

        other = replace(
            first,
            steam_id="99999999999999999",
            name="other",
        )

        analysis = replace(
            analysis,
            players=[
                other,
                first,
            ],
        )

        payload = build_match_ai_payload(
            analysis,
            steam_id="76561198055629469",
        )

        self.assertEqual(
            payload[
                "verified_metrics"
            ][
                "overall"
            ][
                "kills"
            ],
            first.stats.kills,
        )


if __name__ == "__main__":
    unittest.main()

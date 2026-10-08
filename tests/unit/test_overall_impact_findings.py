import unittest

from src.domain.insights import (
    generate_overall_impact_findings,
    generate_player_findings,
)


class TestOverallImpactFindings(
    unittest.TestCase
):
    def test_detects_inferno_stomp_case(
        self,
    ):
        stats = {
            "rounds_played": 14.0,
            "kills": 3.0,
            "deaths": 14.0,
            "damage": 653.8,
            "kast_rounds": 7.0,
            "survived_rounds": 0.0,
        }

        findings = (
            generate_overall_impact_findings(
                stats
            )
        )

        self.assertEqual(
            len(findings),
            1,
        )

        finding = findings[0]

        self.assertEqual(
            finding.code,
            "LOW_OVERALL_IMPACT",
        )

        self.assertEqual(
            finding.kind,
            "weakness",
        )

        self.assertEqual(
            finding.severity,
            "high",
        )

        self.assertEqual(
            finding.evidence[
                "weak_signal_count"
            ],
            4.0,
        )

        self.assertEqual(
            finding.evidence["adr"],
            46.7,
        )

        self.assertEqual(
            finding.evidence[
                "kast_pct"
            ],
            50.0,
        )

        self.assertEqual(
            finding.evidence[
                "survival_pct"
            ],
            0.0,
        )

    def test_three_signals_are_medium(
        self,
    ):
        stats = {
            "rounds_played": 10.0,
            "kills": 3.0,
            "deaths": 10.0,
            "damage": 500.0,
            "kast_rounds": 5.0,
            "survived_rounds": 5.0,
        }

        findings = (
            generate_overall_impact_findings(
                stats
            )
        )

        self.assertEqual(
            len(findings),
            1,
        )

        self.assertEqual(
            findings[0].severity,
            "medium",
        )

        self.assertEqual(
            findings[0].evidence[
                "weak_signal_count"
            ],
            3.0,
        )

    def test_two_weak_metrics_are_not_enough(
        self,
    ):
        stats = {
            "rounds_played": 10.0,
            "kills": 10.0,
            "deaths": 10.0,
            "damage": 500.0,
            "kast_rounds": 5.0,
            "survived_rounds": 3.0,
        }

        self.assertEqual(
            generate_overall_impact_findings(
                stats
            ),
            [],
        )

    def test_short_sample_is_ignored(
        self,
    ):
        stats = {
            "rounds_played": 8.0,
            "kills": 1.0,
            "deaths": 8.0,
            "damage": 200.0,
            "kast_rounds": 2.0,
            "survived_rounds": 0.0,
        }

        self.assertEqual(
            generate_overall_impact_findings(
                stats
            ),
            [],
        )

    def test_player_findings_include_overall_impact(
        self,
    ):
        stats = {
            "rounds_played": 14.0,
            "kills": 3.0,
            "deaths": 14.0,
            "damage": 653.8,
            "kast_rounds": 7.0,
            "survived_rounds": 0.0,
        }

        findings = generate_player_findings(
            {},
            overall_stats=stats,
        )

        self.assertIn(
            "LOW_OVERALL_IMPACT",
            {
                finding.code
                for finding in findings
            },
        )


if __name__ == "__main__":
    unittest.main()

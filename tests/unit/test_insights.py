import unittest

from src.domain.insights import (
    generate_side_findings,
)


class TestSideFindings(unittest.TestCase):

    def test_detects_weaker_t_side(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "damage": 1200.0,
                "kast_rounds": 10,
            },
            "T": {
                "rounds_played": 12,
                "damage": 720.0,
                "kast_rounds": 6,
            },
        }

        findings = generate_side_findings(
            stats
        )

        self.assertEqual(
            len(findings),
            1,
        )

        self.assertEqual(
            findings[0].code,
            "SIDE_PERFORMANCE_GAP",
        )

        self.assertEqual(
            findings[0].side,
            "T",
        )

        self.assertEqual(
            findings[0].evidence["ct_adr"],
            100.0,
        )

        self.assertEqual(
            findings[0].evidence["t_adr"],
            60.0,
        )

    def test_detects_weaker_ct_side(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "damage": 720.0,
                "kast_rounds": 6,
            },
            "T": {
                "rounds_played": 12,
                "damage": 1200.0,
                "kast_rounds": 10,
            },
        }

        findings = generate_side_findings(
            stats
        )

        self.assertEqual(
            len(findings),
            1,
        )

        self.assertEqual(
            findings[0].side,
            "CT",
        )

    def test_small_gap_creates_no_finding(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "damage": 1080.0,
                "kast_rounds": 9,
            },
            "T": {
                "rounds_played": 12,
                "damage": 960.0,
                "kast_rounds": 8,
            },
        }

        self.assertEqual(
            generate_side_findings(stats),
            [],
        )

    def test_conflicting_signals_create_no_finding(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "damage": 1200.0,
                "kast_rounds": 6,
            },
            "T": {
                "rounds_played": 12,
                "damage": 720.0,
                "kast_rounds": 10,
            },
        }

        self.assertEqual(
            generate_side_findings(stats),
            [],
        )

    def test_insufficient_rounds_create_no_finding(self):
        stats = {
            "CT": {
                "rounds_played": 5,
                "damage": 600.0,
                "kast_rounds": 5,
            },
            "T": {
                "rounds_played": 12,
                "damage": 500.0,
                "kast_rounds": 3,
            },
        }

        self.assertEqual(
            generate_side_findings(stats),
            [],
        )


if __name__ == "__main__":
    unittest.main()

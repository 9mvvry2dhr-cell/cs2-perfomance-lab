import unittest

from src.domain.insights import (
    generate_entry_findings,
    generate_player_findings,
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




class TestEntryFindings(unittest.TestCase):

    def test_detects_frequent_opening_deaths_on_t(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "entry_deaths": 1,
            },
            "T": {
                "rounds_played": 12,
                "entry_deaths": 3,
            },
        }

        findings = generate_entry_findings(
            stats
        )

        self.assertEqual(
            len(findings),
            1,
        )

        self.assertEqual(
            findings[0].code,
            "FREQUENT_OPENING_DEATHS",
        )

        self.assertEqual(
            findings[0].side,
            "T",
        )

        self.assertEqual(
            findings[0].evidence[
                "entry_death_rate_pct"
            ],
            25.0,
        )

    def test_two_opening_deaths_are_not_enough(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "entry_deaths": 2,
            },
            "T": {
                "rounds_played": 12,
                "entry_deaths": 0,
            },
        }

        self.assertEqual(
            generate_entry_findings(stats),
            [],
        )

    def test_high_rate_with_too_few_rounds_is_ignored(self):
        stats = {
            "CT": {
                "rounds_played": 5,
                "entry_deaths": 3,
            },
            "T": {
                "rounds_played": 12,
                "entry_deaths": 0,
            },
        }

        self.assertEqual(
            generate_entry_findings(stats),
            [],
        )

    def test_below_rate_threshold_is_ignored(self):
        stats = {
            "CT": {
                "rounds_played": 16,
                "entry_deaths": 3,
            },
            "T": {
                "rounds_played": 12,
                "entry_deaths": 0,
            },
        }

        self.assertEqual(
            generate_entry_findings(stats),
            [],
        )



    def test_positive_opening_balance_is_not_flagged(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "entry_kills": 5,
                "entry_deaths": 4,
            },
            "T": {
                "rounds_played": 12,
                "entry_kills": 0,
                "entry_deaths": 0,
            },
        }

        self.assertEqual(
            generate_entry_findings(stats),
            [],
        )



    def test_one_death_opening_gap_is_not_flagged(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "entry_kills": 3,
                "entry_deaths": 4,
            },
            "T": {
                "rounds_played": 12,
                "entry_kills": 0,
                "entry_deaths": 0,
            },
        }

        self.assertEqual(
            generate_entry_findings(stats),
            [],
        )




class TestPlayerFindings(unittest.TestCase):

    def test_combines_side_and_entry_findings(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "damage": 1200.0,
                "kast_rounds": 10,
                "entry_kills": 2,
                "entry_deaths": 1,
            },
            "T": {
                "rounds_played": 12,
                "damage": 600.0,
                "kast_rounds": 6,
                "entry_kills": 0,
                "entry_deaths": 4,
            },
        }

        findings = generate_player_findings(
            stats
        )

        self.assertEqual(
            [finding.code for finding in findings],
            [
                "SIDE_PERFORMANCE_GAP",
                "FREQUENT_OPENING_DEATHS",
            ],
        )

        self.assertEqual(
            findings[0].side,
            "T",
        )

        self.assertEqual(
            findings[1].side,
            "T",
        )

    def test_returns_empty_when_no_rules_match(self):
        stats = {
            "CT": {
                "rounds_played": 12,
                "damage": 900.0,
                "kast_rounds": 9,
                "entry_kills": 2,
                "entry_deaths": 1,
            },
            "T": {
                "rounds_played": 12,
                "damage": 850.0,
                "kast_rounds": 9,
                "entry_kills": 1,
                "entry_deaths": 1,
            },
        }

        self.assertEqual(
            generate_player_findings(stats),
            [],
        )


if __name__ == "__main__":
    unittest.main()

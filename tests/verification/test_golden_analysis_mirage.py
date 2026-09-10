import json
import os
import unittest
from dataclasses import asdict
from pathlib import Path

from src.domain.analysis import build_match_analysis
from src.metrics.splits import calculate_split_metrics
from src.parsing.demo_parser import DemoParser


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "mirage_analysis_v1.json"
)

DEMO_ENV = "CS2_GOLDEN_MIRAGE_DEMO"


def normalize_payload(payload):
    payload = dict(payload)

    players = [
        dict(player)
        for player in payload["players"]
    ]

    players.sort(
        key=lambda player: player["steam_id"]
    )

    for player in players:
        player["findings"] = sorted(
            player["findings"],
            key=lambda finding: (
                finding["code"],
                finding["side"],
            ),
        )

    payload["players"] = players

    return payload


class TestGoldenMirageAnalysis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        raw_path = os.environ.get(
            DEMO_ENV
        )

        if not raw_path:
            raise unittest.SkipTest(
                f"{DEMO_ENV} is not set"
            )

        demo_path = Path(
            raw_path
        )

        if not demo_path.exists():
            raise unittest.SkipTest(
                f"Golden demo not found: {demo_path}"
            )

        expected = json.loads(
            FIXTURE_PATH.read_text(
                encoding="utf-8"
            )
        )

        wrapper = DemoParser(
            str(demo_path)
        )

        match = wrapper.parse()

        splits = calculate_split_metrics(
            wrapper.raw_parser,
            [
                player.steam_id
                for player in match.players
            ],
        )

        analysis = build_match_analysis(
            match,
            splits,
        )

        cls.expected = normalize_payload(
            expected
        )

        cls.actual = normalize_payload(
            asdict(analysis)
        )

    def test_full_analysis_matches_golden_fixture(self):
        self.assertEqual(
            self.actual,
            self.expected,
        )


if __name__ == "__main__":
    unittest.main()

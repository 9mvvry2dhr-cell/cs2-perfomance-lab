import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.parsing.demo_parser import DemoParser


DEMO_NAME = (
    "match730_003829381261881770506_"
    "1543614415_187.dem"
)

FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "mirage_expected.json"
)


def find_demo():
    """
    Ищет нашу контрольную demo локально.

    Сам .dem не обязан находиться в Git.
    """

    candidates = [
        PROJECT_ROOT / DEMO_NAME,
        PROJECT_ROOT / "data" / DEMO_NAME,
        PROJECT_ROOT / "demos" / DEMO_NAME,
    ]

    for path in candidates:
        if path.exists():
            return path

    for path in PROJECT_ROOT.rglob(DEMO_NAME):
        if (
            ".venv" not in path.parts
            and ".git" not in path.parts
        ):
            return path

    return None


class TestKnownMirageDemo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        demo_path = find_demo()

        if demo_path is None:
            raise unittest.SkipTest(
                f"Control demo not found: {DEMO_NAME}"
            )

        cls.expected = json.loads(
            FIXTURE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.match = DemoParser(
            str(demo_path)
        ).parse()

        cls.players = {
            player.name: player
            for player in cls.match.players
        }

    def test_match_identity(self):
        expected = self.expected["match"]

        self.assertEqual(
            self.match.map_name,
            expected["map_name"],
        )

        self.assertEqual(
            self.match.rounds_played,
            expected["rounds_played"],
        )

        self.assertEqual(
            self.match.score_ct,
            expected["score_ct"],
        )

        self.assertEqual(
            self.match.score_t,
            expected["score_t"],
        )

        self.assertEqual(
            self.match.is_valid,
            expected["is_valid"],
        )

    def test_expected_players_present(self):
        expected_players = set(
            self.expected["players"].keys()
        )

        actual_players = set(
            self.players.keys()
        )

        self.assertEqual(
            actual_players,
            expected_players,
        )

    def test_player_base_stats(self):
        for name, expected in (
            self.expected["players"].items()
        ):
            with self.subTest(player=name):
                player = self.players[name]

                self.assertEqual(
                    player.kills,
                    expected["kills"],
                )

                self.assertEqual(
                    player.deaths,
                    expected["deaths"],
                )

                self.assertEqual(
                    player.assists,
                    expected["assists"],
                )

                self.assertAlmostEqual(
                    player.damage,
                    expected["damage"],
                    delta=0.01,
                )

    def test_player_utility(self):
        for name, expected in (
            self.expected["players"].items()
        ):
            with self.subTest(player=name):
                player = self.players[name]

                self.assertAlmostEqual(
                    player.he_damage,
                    expected["he_damage"],
                    delta=0.01,
                )

                self.assertAlmostEqual(
                    player.inferno_damage,
                    expected["inferno_damage"],
                    delta=0.01,
                )

                self.assertEqual(
                    player.enemies_flashed,
                    expected["enemies_flashed"],
                )

                # В fixture duration хранится с точностью,
                # которую мы независимо проверяли вручную.
                self.assertAlmostEqual(
                    player.flash_duration,
                    expected["flash_duration"],
                    delta=0.05,
                )

    def test_player_entry(self):
        for name, expected in (
            self.expected["players"].items()
        ):
            with self.subTest(player=name):
                player = self.players[name]

                self.assertEqual(
                    player.entry_kills,
                    expected["entry_kills"],
                )

                self.assertEqual(
                    player.entry_deaths,
                    expected["entry_deaths"],
                )

    def test_player_clutches(self):
        for name, expected in (
            self.expected["players"].items()
        ):
            with self.subTest(player=name):
                player = self.players[name]

                self.assertEqual(
                    player.clutches_won,
                    expected["clutches_won"],
                )
if __name__ == "__main__":
    unittest.main()
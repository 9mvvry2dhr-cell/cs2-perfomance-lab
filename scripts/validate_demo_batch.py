import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

from src.parsing.demo_parser import DemoParser


def validate_demo(demo_path: Path) -> bool:
    print(f"\n{demo_path.name}")

    try:
        match = DemoParser(
            str(demo_path)
        ).parse()

    except Exception as exc:
        print(
            f"  ERROR: {type(exc).__name__}: {exc}"
        )
        return False

    score_total = (
        match.score_ct
        + match.score_t
    )

    total_clutches = sum(
        player.clutches_won
        for player in match.players
    )

    total_entry_kills = sum(
        player.entry_kills
        for player in match.players
    )

    total_entry_deaths = sum(
        player.entry_deaths
        for player in match.players
    )

    total_trade_kills = sum(
        player.trade_kills
        for player in match.players
    )

    total_traded_deaths = sum(
        player.traded_deaths
        for player in match.players
    )

    kast_percentages = [
        (
            player.kast_rounds
            / match.rounds_played
            * 100.0
        )
        for player in match.players
        if match.rounds_played > 0
    ]

    kast_min = (
        min(kast_percentages)
        if kast_percentages
        else 0.0
    )

    kast_max = (
        max(kast_percentages)
        if kast_percentages
        else 0.0
    )

    overtime = (
        match.rounds_played > 24
    )

    checks = {
        "match_valid": match.is_valid,
        "has_rounds": match.rounds_played > 0,
        "score_matches_rounds":
            score_total == match.rounds_played,
        "entry_balanced":
            total_entry_kills == total_entry_deaths,
        "trade_nonnegative": all(
            player.trade_kills >= 0
            and player.traded_deaths >= 0
            for player in match.players
        ),
        "trade_consistent":
            total_trade_kills <= total_traded_deaths,
        "kast_in_range": all(
            0 <= player.kast_rounds <= match.rounds_played
            for player in match.players
        ),
    }

    passed = all(
        checks.values()
    )

    print(
        f"  Status:      "
        f"{'PASS' if passed else 'FAIL'}"
    )
    print(
        f"  Map:         {match.map_name}"
    )
    print(
        f"  Score:       "
        f"{match.score_ct}:{match.score_t}"
    )
    print(
        f"  Rounds:      {match.rounds_played}"
    )
    print(
        f"  Overtime:    "
        f"{'YES' if overtime else 'NO'}"
    )
    print(
        f"  Players:     {len(match.players)}"
    )
    print(
        f"  Entry K/D:   "
        f"{total_entry_kills}/"
        f"{total_entry_deaths}"
    )
    print(
        f"  Clutches:    {total_clutches}"
    )
    print(
        f"  Trade kills: {total_trade_kills}"
    )
    print(
        f"  Traded deaths: "
        f"{total_traded_deaths}"
    )
    print(
        f"  KAST range:  "
        f"{kast_min:.1f}% - {kast_max:.1f}%"
    )

    failed_checks = [
        name
        for name, ok in checks.items()
        if not ok
    ]

    if failed_checks:
        print(
            "  Failed checks: "
            + ", ".join(failed_checks)
        )

    if match.validation_error:
        print(
            f"  Validation:  "
            f"{match.validation_error}"
        )

    return passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run CS2 Performance Lab "
            "Data Trust checks over a directory "
            "of .dem files."
        )
    )

    parser.add_argument(
        "demo_dir",
        type=Path,
        help="Directory containing .dem files",
    )

    args = parser.parse_args()

    if not args.demo_dir.exists():
        print(
            f"Directory not found: "
            f"{args.demo_dir}"
        )
        return 2

    demo_files = sorted(
        args.demo_dir.glob("*.dem")
    )

    if not demo_files:
        print(
            f"No .dem files found in "
            f"{args.demo_dir}"
        )
        return 2

    print(
        f"Found demos: {len(demo_files)}"
    )
    print("=" * 110)

    passed = 0

    for index, demo_path in enumerate(
        demo_files,
        start=1,
    ):
        print(
            f"\n[{index}/{len(demo_files)}]",
            end="",
        )

        if validate_demo(
            demo_path
        ):
            passed += 1

    failed = (
        len(demo_files)
        - passed
    )

    print()
    print("=" * 110)
    print(
        f"RESULT: {passed} passed / "
        f"{failed} failed / "
        f"{len(demo_files)} total"
    )

    return (
        0
        if failed == 0
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

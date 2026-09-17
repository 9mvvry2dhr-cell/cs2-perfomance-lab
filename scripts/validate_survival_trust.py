from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.round_context import (
    build_round_contexts,
    find_round,
    safe_int,
)
from src.parsing.demo_parser import DemoParser


def normalize_sid(value) -> str | None:
    try:
        if value is None or value != value:
            return None
        return str(int(value))
    except Exception:
        value = str(value)
        return value if value else None


def validate_demo(demo_path: Path) -> bool:
    print()
    print("=" * 110)
    print(demo_path.name)

    parser = DemoParser(str(demo_path))

    try:
        match = parser.parse()
    except Exception as exc:
        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )
        return False

    rounds = build_round_contexts(
        parser.raw_parser
    )

    if not rounds:
        print(
            "SURVIVAL CHECK: FAIL - "
            "no confirmed rounds"
        )
        return False

    freeze_ticks = [
        round_data.freeze_end_tick
        for round_data in rounds
    ]

    roster_df = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=freeze_ticks,
    )

    if (
        roster_df is None
        or not hasattr(roster_df, "empty")
        or roster_df.empty
    ):
        print(
            "SURVIVAL CHECK: FAIL - "
            "no roster snapshots"
        )
        return False

    round_by_freeze = {
        round_data.freeze_end_tick:
        round_data.round_num
        for round_data in rounds
    }

    roster_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    participation = Counter()

    for _, row in roster_df.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_num = round_by_freeze.get(
            tick
        )

        if round_num is None:
            continue

        steam_id = normalize_sid(
            row.get("steamid")
        )

        team_num = safe_int(
            row.get("team_num"),
            default=0,
        )

        if (
            steam_id is None
            or team_num not in {2, 3}
        ):
            continue

        if (
            steam_id
            not in roster_by_round[round_num]
        ):
            roster_by_round[
                round_num
            ].add(
                steam_id
            )

            participation[
                steam_id
            ] += 1

    deaths = parser.raw_parser.parse_event(
        "player_death"
    )

    if deaths is None:
        print(
            "SURVIVAL CHECK: FAIL - "
            "missing player_death events"
        )
        return False

    deaths = deaths.copy()

    deaths["_event_order"] = range(
        len(deaths)
    )

    deaths = deaths.sort_values(
        [
            "tick",
            "_event_order",
        ],
        kind="stable",
    )

    dead_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    for _, row in deaths.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_context = find_round(
            tick,
            rounds,
        )

        if round_context is None:
            continue

        round_num = (
            round_context.round_num
        )

        victim = normalize_sid(
            row.get("user_steamid")
        )

        if (
            victim is None
            or victim
            not in roster_by_round[round_num]
        ):
            continue

        dead_by_round[
            round_num
        ].add(
            victim
        )

    survived = Counter()
    died = Counter()

    for round_data in rounds:
        round_num = (
            round_data.round_num
        )

        for steam_id in (
            roster_by_round[round_num]
        ):
            if (
                steam_id
                in dead_by_round[round_num]
            ):
                died[
                    steam_id
                ] += 1
            else:
                survived[
                    steam_id
                ] += 1

    mismatches = []
    invariant_errors = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual = survived[
            steam_id
        ]

        expected = int(
            player.survived_rounds
        )

        if actual != expected:
            mismatches.append(
                (
                    player.name,
                    steam_id,
                    actual,
                    expected,
                )
            )

        participated = participation[
            steam_id
        ]

        reconstructed = (
            survived[steam_id]
            + died[steam_id]
        )

        if (
            reconstructed
            != participated
        ):
            invariant_errors.append(
                (
                    player.name,
                    steam_id,
                    reconstructed,
                    participated,
                )
            )

        if (
            participated
            != int(player.rounds_played)
        ):
            invariant_errors.append(
                (
                    player.name,
                    steam_id,
                    participated,
                    int(player.rounds_played),
                )
            )

    total_participated = sum(
        participation.values()
    )

    total_survived = sum(
        survived.values()
    )

    total_died = sum(
        died.values()
    )

    print(
        f"Map:       {match.map_name}"
    )

    print(
        f"Score:     "
        f"{match.score_ct}:"
        f"{match.score_t}"
    )

    print(
        f"Rounds:    "
        f"{match.rounds_played}"
    )

    print(
        f"Player R:  "
        f"{total_participated}"
    )

    print(
        f"Survived:  "
        f"{total_survived}"
    )

    print(
        f"Died:      "
        f"{total_died}"
    )

    print(
        f"Balance:   "
        f"{total_survived + total_died}"
    )

    if (
        mismatches
        or invariant_errors
    ):
        print(
            "Survival:  FAIL"
        )

        for mismatch in mismatches:
            print(
                "  mismatch:",
                mismatch,
            )

        for error in invariant_errors:
            print(
                "  invariant:",
                error,
            )

        return False

    print(
        "Survival:  PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify CS2 "
            "survived rounds from freeze-end "
            "participation and raw deaths."
        )
    )

    parser.add_argument(
        "demo_dir",
        type=Path,
        help="Directory containing .dem files",
    )

    args = parser.parse_args()

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

    passed = 0

    for demo_path in demo_files:
        if validate_demo(demo_path):
            passed += 1

    failed = (
        len(demo_files)
        - passed
    )

    print()
    print("=" * 110)

    print(
        f"RESULT: "
        f"{passed} passed / "
        f"{failed} failed / "
        f"{len(demo_files)} total"
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

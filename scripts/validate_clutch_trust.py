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

    parser = DemoParser(
        str(demo_path)
    )

    try:
        match = parser.parse()

    except Exception as exc:
        print(
            f"ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return False

    rounds = build_round_contexts(
        parser.raw_parser
    )

    if not rounds:
        print(
            "CLUTCH CHECK: FAIL - "
            "no confirmed rounds"
        )
        return False

    snapshot_ticks = [
        round_data.freeze_end_tick
        for round_data in rounds
    ]

    teams_df = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=snapshot_ticks,
    )

    if (
        teams_df is None
        or not hasattr(teams_df, "empty")
        or teams_df.empty
    ):
        print(
            "CLUTCH CHECK: FAIL - "
            "no team snapshots"
        )
        return False

    teams_by_round = {
        round_data.round_num: {
            2: set(),
            3: set(),
        }
        for round_data in rounds
    }

    round_by_tick = {
        round_data.freeze_end_tick:
        round_data.round_num
        for round_data in rounds
    }

    for _, row in teams_df.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_num = round_by_tick.get(
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
            steam_id is not None
            and team_num in {2, 3}
        ):
            teams_by_round[
                round_num
            ][team_num].add(
                steam_id
            )

    deaths = parser.raw_parser.parse_event(
        "player_death"
    )

    if (
        deaths is None
        or not hasattr(deaths, "empty")
        or deaths.empty
    ):
        print(
            "CLUTCH CHECK: FAIL - "
            "no player_death events"
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

    clutch_counts = Counter()
    clutch_rounds = []

    for round_data in rounds:
        if round_data.winner_team not in {2, 3}:
            continue

        alive = {
            2: set(
                teams_by_round[
                    round_data.round_num
                ][2]
            ),
            3: set(
                teams_by_round[
                    round_data.round_num
                ][3]
            ),
        }

        if (
            not alive[2]
            or not alive[3]
        ):
            continue

        candidates = {}

        def detect_candidates():
            for team_num in (2, 3):
                enemy_team = (
                    3
                    if team_num == 2
                    else 2
                )

                if len(
                    alive[team_num]
                ) != 1:
                    continue

                enemy_count = len(
                    alive[enemy_team]
                )

                if enemy_count <= 0:
                    continue

                player = next(
                    iter(
                        alive[team_num]
                    )
                )

                if player not in candidates:
                    candidates[player] = (
                        team_num,
                        enemy_count,
                    )

        detect_candidates()

        round_deaths = deaths[
            (
                deaths["tick"]
                >= round_data.start_tick
            )
            & (
                deaths["tick"]
                <= round_data.end_tick
            )
        ]

        for _, row in round_deaths.iterrows():
            victim = normalize_sid(
                row.get("user_steamid")
            )

            if victim is None:
                continue

            alive[2].discard(
                victim
            )

            alive[3].discard(
                victim
            )

            detect_candidates()

        for player, (
            team_num,
            enemy_count,
        ) in candidates.items():

            if (
                team_num
                != round_data.winner_team
            ):
                continue

            if player not in alive[
                team_num
            ]:
                continue

            clutch_counts[
                player
            ] += 1

            clutch_rounds.append(
                (
                    round_data.round_num,
                    player,
                    enemy_count,
                )
            )

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual = clutch_counts[
            steam_id
        ]

        expected = int(
            player.clutches_won
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
        f"Clutches:  "
        f"{len(clutch_rounds)}"
    )

    if clutch_rounds:
        print(
            "Situations: "
            + ", ".join(
                f"R{round_num}:1v{enemy_count}"
                for (
                    round_num,
                    _,
                    enemy_count,
                ) in clutch_rounds
            )
        )

    if mismatches:
        print(
            "Clutch:    FAIL"
        )

        for mismatch in mismatches:
            print(
                "  ",
                mismatch,
            )

        return False

    print(
        "Clutch:    PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify CS2 "
            "clutch wins against raw "
            "round and death events."
        )
    )

    parser.add_argument(
        "demo_dir",
        type=Path,
        help=(
            "Directory containing .dem files"
        ),
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
        f"Found demos: "
        f"{len(demo_files)}"
    )

    passed = 0

    for demo_path in demo_files:
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
        f"RESULT: "
        f"{passed} passed / "
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

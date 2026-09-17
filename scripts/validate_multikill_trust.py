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
            "MULTIKILL CHECK: FAIL - "
            "no confirmed rounds"
        )
        return False

    deaths = parser.raw_parser.parse_event(
        "player_death"
    )

    if (
        deaths is None
        or not hasattr(deaths, "empty")
        or deaths.empty
    ):
        print(
            "MULTIKILL CHECK: FAIL - "
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

    death_ticks = sorted({
        safe_int(
            row.get("tick"),
            default=-1,
        )
        for _, row in deaths.iterrows()
        if safe_int(
            row.get("tick"),
            default=-1,
        ) >= 0
    })

    teams_df = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=death_ticks,
    )

    if (
        teams_df is None
        or not hasattr(teams_df, "empty")
        or teams_df.empty
    ):
        print(
            "MULTIKILL CHECK: FAIL - "
            "no team snapshots"
        )
        return False

    teams = {}

    for _, row in teams_df.iterrows():
        steam_id = normalize_sid(
            row.get("steamid")
        )

        if steam_id is None:
            continue

        teams[
            (
                safe_int(
                    row.get("tick"),
                    default=-1,
                ),
                steam_id,
            )
        ] = safe_int(
            row.get("team_num"),
            default=0,
        )

    kills_by_round_player = Counter()

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

        attacker = normalize_sid(
            row.get("attacker_steamid")
        )

        victim = normalize_sid(
            row.get("user_steamid")
        )

        if (
            attacker is None
            or victim is None
            or attacker == victim
        ):
            continue

        attacker_team = teams.get(
            (tick, attacker),
            0,
        )

        victim_team = teams.get(
            (tick, victim),
            0,
        )

        if (
            attacker_team not in {2, 3}
            or victim_team not in {2, 3}
            or attacker_team == victim_team
        ):
            continue

        kills_by_round_player[
            (
                round_context.round_num,
                attacker,
            )
        ] += 1

    two_k = Counter()
    three_k = Counter()
    four_k = Counter()
    five_k = Counter()

    for (
        round_num,
        steam_id,
    ), kills in kills_by_round_player.items():

        if kills == 2:
            two_k[steam_id] += 1

        elif kills == 3:
            three_k[steam_id] += 1

        elif kills == 4:
            four_k[steam_id] += 1

        elif kills == 5:
            five_k[steam_id] += 1

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual = {
            "2K": two_k[steam_id],
            "3K": three_k[steam_id],
            "4K": four_k[steam_id],
            "5K": five_k[steam_id],
        }

        expected = {
            "2K": int(
                player.two_k_rounds
            ),
            "3K": int(
                player.three_k_rounds
            ),
            "4K": int(
                player.four_k_rounds
            ),
            "5K": int(
                player.five_k_rounds
            ),
        }

        diff = {}

        for key in actual:
            if actual[key] != expected[key]:
                diff[key] = (
                    actual[key],
                    expected[key],
                )

        if diff:
            mismatches.append(
                (
                    player.name,
                    steam_id,
                    diff,
                )
            )

    total_2k = sum(
        two_k.values()
    )

    total_3k = sum(
        three_k.values()
    )

    total_4k = sum(
        four_k.values()
    )

    total_5k = sum(
        five_k.values()
    )

    weighted_kills = (
        total_2k * 2
        + total_3k * 3
        + total_4k * 4
        + total_5k * 5
    )

    total_enemy_kills = sum(
        kills_by_round_player.values()
    )

    invariant_ok = (
        weighted_kills
        <= total_enemy_kills
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
        f"2K:        {total_2k}"
    )

    print(
        f"3K:        {total_3k}"
    )

    print(
        f"4K:        {total_4k}"
    )

    print(
        f"5K:        {total_5k}"
    )

    print(
        f"Weighted:  {weighted_kills}"
    )

    print(
        f"Enemy K:   {total_enemy_kills}"
    )

    if (
        mismatches
        or not invariant_ok
    ):
        print(
            "Multikill: FAIL"
        )

        if not invariant_ok:
            print(
                "  invariant:",
                weighted_kills,
                ">",
                total_enemy_kills,
            )

        for mismatch in mismatches:
            print(
                " ",
                mismatch,
            )

        return False

    print(
        "Multikill: PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify exact "
            "2K/3K/4K/5K rounds from "
            "confirmed enemy kills."
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

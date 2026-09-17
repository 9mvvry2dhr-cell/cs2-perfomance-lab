from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.round_context import (
    build_round_contexts,
    find_round,
    safe_float,
    safe_int,
)
from src.parsing.demo_parser import DemoParser


TRADE_WINDOW_SECONDS = 5.0


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
            "KAST CHECK: FAIL - "
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
            "KAST CHECK: FAIL - "
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
            steam_id is not None
            and team_num in {2, 3}
        ):
            roster_by_round[
                round_num
            ].add(
                steam_id
            )

    deaths = parser.raw_parser.parse_event(
        "player_death",
        other=["game_time"],
    )

    if (
        deaths is None
        or not hasattr(deaths, "empty")
        or deaths.empty
    ):
        print(
            "KAST CHECK: FAIL - "
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

    team_df = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=death_ticks,
    )

    if (
        team_df is None
        or not hasattr(team_df, "empty")
        or team_df.empty
    ):
        print(
            "KAST CHECK: FAIL - "
            "no team snapshots"
        )
        return False

    teams = {}

    for _, row in team_df.iterrows():
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

    kill_rounds = defaultdict(set)
    assist_rounds = defaultdict(set)
    survive_rounds = defaultdict(set)
    traded_rounds = defaultdict(set)

    dead_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    confirmed_enemy_kills = []

    for _, row in deaths.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        game_time = safe_float(
            row.get("game_time"),
            default=-1.0,
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

        attacker = normalize_sid(
            row.get("attacker_steamid")
        )

        victim = normalize_sid(
            row.get("user_steamid")
        )

        assister = normalize_sid(
            row.get("assister_steamid")
        )

        if (
            victim is not None
            and victim
            in roster_by_round[round_num]
        ):
            dead_by_round[
                round_num
            ].add(
                victim
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

        if (
            attacker
            in roster_by_round[round_num]
        ):
            kill_rounds[
                attacker
            ].add(
                round_num
            )

        if assister is not None:
            assister_team = teams.get(
                (tick, assister),
                0,
            )

            if (
                assister
                in roster_by_round[round_num]
                and assister_team in {2, 3}
                and assister_team != victim_team
            ):
                assist_rounds[
                    assister
                ].add(
                    round_num
                )

        confirmed_enemy_kills.append(
            {
                "round_num": round_num,
                "tick": tick,
                "game_time": game_time,
                "attacker": attacker,
                "victim": victim,
                "victim_team": victim_team,
            }
        )

    # Survival
    for round_data in rounds:
        round_num = (
            round_data.round_num
        )

        survivors = (
            roster_by_round[
                round_num
            ]
            - dead_by_round[
                round_num
            ]
        )

        for player in survivors:
            survive_rounds[
                player
            ].add(
                round_num
            )

    # Independent traded-death detection
    for index, death in enumerate(
        confirmed_enemy_kills
    ):
        if death["game_time"] < 0:
            continue

        original_killer = death[
            "attacker"
        ]

        dead_player = death[
            "victim"
        ]

        for retaliation in (
            confirmed_enemy_kills[
                index + 1:
            ]
        ):
            if (
                retaliation["round_num"]
                != death["round_num"]
            ):
                if (
                    retaliation["round_num"]
                    > death["round_num"]
                ):
                    break

                continue

            if (
                retaliation["game_time"]
                < 0
            ):
                continue

            elapsed = (
                retaliation["game_time"]
                - death["game_time"]
            )

            if elapsed < 0:
                continue

            if (
                elapsed
                > TRADE_WINDOW_SECONDS
            ):
                break

            if (
                retaliation["victim"]
                != original_killer
            ):
                continue

            trader = retaliation[
                "attacker"
            ]

            trader_team = teams.get(
                (
                    retaliation["tick"],
                    trader,
                ),
                0,
            )

            if (
                trader_team
                != death["victim_team"]
            ):
                continue

            if (
                dead_player
                in roster_by_round[
                    death["round_num"]
                ]
            ):
                traded_rounds[
                    dead_player
                ].add(
                    death["round_num"]
                )

            break

    all_ids = {
        str(player.steam_id)
        for player in match.players
    }

    kast_rounds = {}

    for player in all_ids:
        kast_rounds[player] = (
            kill_rounds[player]
            | assist_rounds[player]
            | survive_rounds[player]
            | traded_rounds[player]
        )

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual = len(
            kast_rounds[
                steam_id
            ]
        )

        expected = int(
            player.kast_rounds
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

    total_k = sum(
        len(value)
        for value in kill_rounds.values()
    )

    total_a = sum(
        len(value)
        for value in assist_rounds.values()
    )

    total_s = sum(
        len(value)
        for value in survive_rounds.values()
    )

    total_t = sum(
        len(value)
        for value in traded_rounds.values()
    )

    total_kast = sum(
        len(value)
        for value in kast_rounds.values()
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
        f"K-rounds:  {total_k}"
    )

    print(
        f"A-rounds:  {total_a}"
    )

    print(
        f"S-rounds:  {total_s}"
    )

    print(
        f"T-rounds:  {total_t}"
    )

    print(
        f"KAST+:     {total_kast}"
    )

    if mismatches:
        print(
            "KAST:      FAIL"
        )

        for mismatch in mismatches:
            print(
                "  ",
                mismatch,
            )

        return False

    print(
        "KAST:      PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify CS2 "
            "KAST-positive rounds from "
            "raw kill, assist, survival "
            "and trade evidence."
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
        f"Found demos: "
        f"{len(demo_files)}"
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

    return (
        0
        if failed == 0
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

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
            "TRADE CHECK: FAIL - "
            "no confirmed rounds"
        )
        return False

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
            "TRADE CHECK: FAIL - "
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

    snapshots = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=death_ticks,
    )

    if (
        snapshots is None
        or not hasattr(snapshots, "empty")
        or snapshots.empty
    ):
        print(
            "TRADE CHECK: FAIL - "
            "no team snapshots"
        )
        return False

    snapshots = snapshots.copy()

    snapshots["_sid"] = snapshots[
        "steamid"
    ].apply(normalize_sid)

    teams = {}

    for _, row in snapshots.iterrows():
        steam_id = row["_sid"]

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

    # ----------------------------------------------------------
    # Confirmed enemy kills only
    # ----------------------------------------------------------

    confirmed = []

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

        if (
            tick < 0
            or game_time < 0
            or round_context is None
        ):
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

        confirmed.append(
            {
                "event_order": safe_int(
                    row.get("_event_order"),
                    default=-1,
                ),
                "round_num": (
                    round_context.round_num
                ),
                "tick": tick,
                "game_time": game_time,
                "attacker": attacker,
                "victim": victim,
                "victim_team": victim_team,
            }
        )

    # ----------------------------------------------------------
    # Detect traded deaths
    # ----------------------------------------------------------

    trade_events = []

    for index, death in enumerate(
        confirmed
    ):
        original_killer = death[
            "attacker"
        ]

        dead_player = death[
            "victim"
        ]

        for retaliation in confirmed[
            index + 1:
        ]:
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

            # The original killer
            # must die.
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

            # Trader must belong
            # to original victim's team.
            if (
                trader_team
                != death["victim_team"]
            ):
                continue

            trade_events.append(
                {
                    "victim": dead_player,
                    "trader": trader,
                    "original_killer": (
                        original_killer
                    ),
                    "death_tick": (
                        death["tick"]
                    ),
                    "retaliation_tick": (
                        retaliation["tick"]
                    ),
                    "retaliation_order": (
                        retaliation[
                            "event_order"
                        ]
                    ),
                    "elapsed": elapsed,
                }
            )

            # First valid retaliation
            # closes this death.
            break

    # ----------------------------------------------------------
    # Aggregate
    # ----------------------------------------------------------

    traded_deaths = Counter()
    trade_kills = Counter()
    retaliation_counter = Counter()

    for event in trade_events:
        traded_deaths[
            event["victim"]
        ] += 1

        retaliation_key = (
            event["retaliation_order"],
            event["retaliation_tick"],
            event["trader"],
            event["original_killer"],
        )

        retaliation_counter[
            retaliation_key
        ] += 1

    # One retaliation kill may trade
    # several deaths, but remains
    # one trade kill.
    for retaliation_key in (
        retaliation_counter
    ):
        trader = retaliation_key[2]

        trade_kills[
            trader
        ] += 1

    # ----------------------------------------------------------
    # Compare against ParsedPlayer
    # ----------------------------------------------------------

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual_kills = trade_kills[
            steam_id
        ]

        actual_deaths = traded_deaths[
            steam_id
        ]

        expected_kills = int(
            player.trade_kills
        )

        expected_deaths = int(
            player.traded_deaths
        )

        diff = {}

        if (
            actual_kills
            != expected_kills
        ):
            diff["trade_kills"] = (
                actual_kills,
                expected_kills,
            )

        if (
            actual_deaths
            != expected_deaths
        ):
            diff["traded_deaths"] = (
                actual_deaths,
                expected_deaths,
            )

        if diff:
            mismatches.append(
                (
                    player.name,
                    steam_id,
                    diff,
                )
            )

    multi_trade_kills = sum(
        1
        for count
        in retaliation_counter.values()
        if count > 1
    )

    max_trade_chain = max(
        retaliation_counter.values(),
        default=0,
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
        f"Trade K:   "
        f"{sum(trade_kills.values())}"
    )

    print(
        f"Traded D:  "
        f"{sum(traded_deaths.values())}"
    )

    print(
        f"Multi:     "
        f"{multi_trade_kills}"
    )

    print(
        f"Max chain: "
        f"{max_trade_chain}"
    )

    if mismatches:
        print(
            "Trades:    FAIL"
        )

        for mismatch in mismatches:
            print(
                "  ",
                mismatch,
            )

        return False

    print(
        "Trades:    PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify CS2 "
            "trade kills and traded deaths "
            "against raw death events."
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

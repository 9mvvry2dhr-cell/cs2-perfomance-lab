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
            "ENTRY CHECK: FAIL - "
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
            "ENTRY CHECK: FAIL - "
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

    event_ticks = sorted({
        safe_int(
            row.get("tick"),
            default=-1,
        )
        for _, row in deaths.iterrows()
        if find_round(
            row.get("tick"),
            rounds,
        ) is not None
    })

    if not event_ticks:
        print(
            "ENTRY CHECK: FAIL - "
            "no in-round death events"
        )
        return False

    snapshots = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=event_ticks,
    )

    if (
        snapshots is None
        or not hasattr(snapshots, "empty")
        or snapshots.empty
    ):
        print(
            "ENTRY CHECK: FAIL - "
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

    opened_rounds = set()
    blocked_rounds = set()

    entry_kills = Counter()
    entry_deaths = Counter()

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

        if (
            round_num in opened_rounds
            or round_num in blocked_rounds
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

        # Fail closed:
        # if team relation cannot be verified,
        # do not guess the entry for this round.
        if (
            attacker_team not in {2, 3}
            or victim_team not in {2, 3}
        ):
            blocked_rounds.add(
                round_num
            )
            continue

        # Suicide/teamkill is not an entry.
        if attacker_team == victim_team:
            continue

        # First confirmed enemy kill of the round.
        entry_kills[
            attacker
        ] += 1

        entry_deaths[
            victim
        ] += 1

        opened_rounds.add(
            round_num
        )

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual_kills = entry_kills[
            steam_id
        ]

        actual_deaths = entry_deaths[
            steam_id
        ]

        expected_kills = int(
            player.entry_kills
        )

        expected_deaths = int(
            player.entry_deaths
        )

        diff = {}

        if actual_kills != expected_kills:
            diff["entry_kills"] = (
                actual_kills,
                expected_kills,
            )

        if actual_deaths != expected_deaths:
            diff["entry_deaths"] = (
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
        f"Entries:   "
        f"{sum(entry_kills.values())}/"
        f"{sum(entry_deaths.values())}"
    )

    if blocked_rounds:
        print(
            "Blocked:   "
            + ", ".join(
                str(value)
                for value in sorted(
                    blocked_rounds
                )
            )
        )

    if mismatches:
        print(
            "Entry:     FAIL"
        )

        for mismatch in mismatches:
            print(
                "  ",
                mismatch,
            )

        return False

    print(
        "Entry:     PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify CS2 "
            "entry kills and entry deaths "
            "against raw player_death events."
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

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


UTILITY_WEAPONS = {
    "hegrenade": "he",
    "inferno": "fire",
    "molotov": "fire",
    "incgrenade": "fire",
}


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
            "UTILITY CHECK: FAIL - "
            "no confirmed rounds"
        )
        return False

    hurt = parser.raw_parser.parse_event(
        "player_hurt"
    )

    blind = parser.raw_parser.parse_event(
        "player_blind"
    )

    if hurt is None or blind is None:
        print(
            "UTILITY CHECK: FAIL - "
            "missing raw events"
        )
        return False

    hurt = hurt.copy()
    blind = blind.copy()

    hurt["_event_order"] = range(
        len(hurt)
    )

    hurt = hurt.sort_values(
        [
            "tick",
            "_event_order",
        ],
        kind="stable",
    )

    event_ticks = set()

    for _, row in hurt.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        if find_round(
            tick,
            rounds,
        ) is not None:
            event_ticks.add(tick)

    for _, row in blind.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        if find_round(
            tick,
            rounds,
        ) is not None:
            event_ticks.add(tick)

    snapshots = parser.raw_parser.parse_ticks(
        ["team_num"],
        ticks=sorted(event_ticks),
    )

    if (
        snapshots is None
        or not hasattr(snapshots, "empty")
        or snapshots.empty
    ):
        print(
            "UTILITY CHECK: FAIL - "
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

    stats = defaultdict(
        lambda: {
            "he_damage": 0.0,
            "inferno_damage": 0.0,
            "enemies_flashed": 0,
            "flash_duration": 0.0,
        }
    )

    health_state = {}

    # ----------------------------------------------------------
    # HE / FIRE DAMAGE
    # ----------------------------------------------------------

    for _, row in hurt.iterrows():
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

        if victim is None:
            continue

        raw_damage = max(
            0.0,
            safe_float(
                row.get("dmg_health"),
                default=0.0,
            ),
        )

        current_health = max(
            0.0,
            safe_float(
                row.get("health"),
                default=0.0,
            ),
        )

        health_key = (
            round_context.round_num,
            victim,
        )

        previous_health = health_state.get(
            health_key,
            100.0,
        )

        actual_damage = min(
            raw_damage,
            max(previous_health, 0.0),
        )

        # Update HP after every hurt event,
        # not only utility damage.
        health_state[
            health_key
        ] = current_health

        weapon = str(
            row.get(
                "weapon",
                "",
            )
        ).lower()

        utility_type = UTILITY_WEAPONS.get(
            weapon
        )

        if (
            utility_type is None
            or attacker is None
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

        # Only enemy utility damage.
        if (
            attacker == victim
            or attacker_team not in {2, 3}
            or victim_team not in {2, 3}
            or attacker_team == victim_team
        ):
            continue

        if utility_type == "he":
            stats[
                attacker
            ]["he_damage"] += actual_damage

        else:
            stats[
                attacker
            ]["inferno_damage"] += actual_damage

    # ----------------------------------------------------------
    # FLASH
    # ----------------------------------------------------------

    blind = blind.sort_values(
        "tick",
        kind="stable",
    )

    for _, row in blind.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        if find_round(
            tick,
            rounds,
        ) is None:
            continue

        attacker = normalize_sid(
            row.get("attacker_steamid")
        )

        victim = normalize_sid(
            row.get("user_steamid")
        )

        duration = safe_float(
            row.get("blind_duration"),
            default=0.0,
        )

        if (
            attacker is None
            or victim is None
            or duration <= 0
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

        # Only enemy flashes.
        if (
            attacker == victim
            or attacker_team not in {2, 3}
            or victim_team not in {2, 3}
            or attacker_team == victim_team
        ):
            continue

        stats[
            attacker
        ]["enemies_flashed"] += 1

        stats[
            attacker
        ]["flash_duration"] += duration

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        actual = stats[
            steam_id
        ]

        diff = {}

        if abs(
            actual["he_damage"]
            - float(player.he_damage)
        ) > 0.01:
            diff["he_damage"] = (
                actual["he_damage"],
                float(player.he_damage),
            )

        if abs(
            actual["inferno_damage"]
            - float(player.inferno_damage)
        ) > 0.01:
            diff["inferno_damage"] = (
                actual["inferno_damage"],
                float(player.inferno_damage),
            )

        if (
            actual["enemies_flashed"]
            != int(player.enemies_flashed)
        ):
            diff["enemies_flashed"] = (
                actual["enemies_flashed"],
                int(player.enemies_flashed),
            )

        if abs(
            actual["flash_duration"]
            - float(player.flash_duration)
        ) > 0.01:
            diff["flash_duration"] = (
                actual["flash_duration"],
                float(player.flash_duration),
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

    if mismatches:
        print(
            "Utility:   FAIL"
        )

        for mismatch in mismatches:
            print(
                "  ",
                mismatch,
            )

        return False

    print(
        "Utility:   PASS"
    )
    print(
        "Status:    PASS"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify CS2 "
            "HE damage, fire damage and "
            "enemy flash metrics against "
            "raw demo events."
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

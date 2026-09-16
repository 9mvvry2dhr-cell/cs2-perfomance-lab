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
    safe_float,
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

        if not value:
            return None

        return value


def build_team_snapshots(
    parser,
    ticks: list[int],
) -> dict[tuple[int, str], int]:
    if not ticks:
        return {}

    snapshots = parser.parse_ticks(
        ["team_num"],
        ticks=ticks,
    )

    if (
        snapshots is None
        or not hasattr(snapshots, "empty")
        or snapshots.empty
    ):
        return {}

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

    return teams


def validate_kda_hs(
    demo_parser: DemoParser,
    match,
    rounds,
) -> list[tuple]:
    deaths_df = demo_parser.raw_parser.parse_event(
        "player_death"
    )

    if (
        deaths_df is None
        or not hasattr(deaths_df, "empty")
        or deaths_df.empty
    ):
        return [
            (
                "missing_player_death",
                None,
            )
        ]

    match_start = rounds[0].start_tick
    match_end = rounds[-1].end_tick

    official = deaths_df[
        (deaths_df["tick"] >= match_start)
        & (deaths_df["tick"] <= match_end)
    ].copy()

    ticks = sorted(
        official["tick"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    teams = build_team_snapshots(
        demo_parser.raw_parser,
        ticks,
    )

    kills = Counter()
    deaths = Counter()
    assists = Counter()
    headshots = Counter()

    for _, row in official.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
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

        attacker_team = teams.get(
            (tick, attacker),
            0,
        )

        victim_team = teams.get(
            (tick, victim),
            0,
        )

        assister_team = teams.get(
            (tick, assister),
            0,
        )

        if victim:
            deaths[victim] += 1

        valid_kill = (
            attacker
            and victim
            and attacker != victim
            and attacker_team in {2, 3}
            and victim_team in {2, 3}
            and attacker_team != victim_team
        )

        if valid_kill:
            kills[attacker] += 1

            if bool(
                row.get(
                    "headshot",
                    False,
                )
            ):
                headshots[attacker] += 1

        # Scoreboard assist is relative to the victim's team.
        #
        # An assister may still receive credit when the final
        # attacker performs a teamkill, so attacker_team is not
        # part of this validation rule.
        valid_assist = (
            assister
            and victim
            and assister != victim
            and assister_team in {2, 3}
            and victim_team in {2, 3}
            and assister_team != victim_team
        )

        if valid_assist:
            assists[assister] += 1

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        expected = {
            "kills": player.kills,
            "deaths": player.deaths,
            "assists": player.assists,
            "headshots": player.headshots,
        }

        actual = {
            "kills": kills[steam_id],
            "deaths": deaths[steam_id],
            "assists": assists[steam_id],
            "headshots": headshots[steam_id],
        }

        diff = {
            key: (
                actual[key],
                expected[key],
            )
            for key in expected
            if actual[key] != expected[key]
        }

        if diff:
            mismatches.append(
                (
                    player.name,
                    steam_id,
                    diff,
                )
            )

    return mismatches


def validate_damage(
    demo_parser: DemoParser,
    match,
    rounds,
) -> list[tuple]:
    hurt = demo_parser.raw_parser.parse_event(
        "player_hurt"
    )

    if (
        hurt is None
        or not hasattr(hurt, "empty")
        or hurt.empty
    ):
        return [
            (
                "missing_player_hurt",
                None,
            )
        ]

    match_start = rounds[0].start_tick
    match_end = rounds[-1].end_tick

    hurt = hurt.copy()
    hurt["_event_order"] = range(
        len(hurt)
    )

    hurt = hurt[
        (hurt["tick"] >= match_start)
        & (hurt["tick"] <= match_end)
    ].copy()

    hurt = hurt.sort_values(
        [
            "tick",
            "_event_order",
        ]
    )

    ticks = sorted(
        hurt["tick"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    teams = build_team_snapshots(
        demo_parser.raw_parser,
        ticks,
    )

    round_starts = [
        (
            round_data.start_tick,
            round_data.round_num,
        )
        for round_data in rounds
    ]

    def round_for_tick(
        tick: int,
    ) -> int | None:
        result = None

        for start_tick, round_num in round_starts:
            if start_tick <= tick:
                result = round_num
            else:
                break

        return result

    health_state = {}
    damage = Counter()
    enemy_hits = Counter()

    for _, row in hurt.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        attacker = normalize_sid(
            row.get("attacker_steamid")
        )

        victim = normalize_sid(
            row.get("user_steamid")
        )

        if victim is None:
            continue

        round_num = round_for_tick(
            tick
        )

        if round_num is None:
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
            round_num,
            victim,
        )

        previous_health = (
            health_state.get(
                health_key,
                100.0,
            )
        )

        actual_damage = min(
            raw_damage,
            max(
                previous_health,
                0.0,
            ),
        )

        # Update HP after every hurt event so overkill
        # clamping remains independent from attacker relation.
        health_state[
            health_key
        ] = current_health

        if attacker is None:
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
            attacker != victim
            and attacker_team in {2, 3}
            and victim_team in {2, 3}
            and attacker_team != victim_team
        ):
            damage[
                attacker
            ] += actual_damage

            enemy_hits[
                attacker
            ] += 1

    mismatches = []

    for player in match.players:
        steam_id = str(
            player.steam_id
        )

        event_damage = float(
            damage[steam_id]
        )

        scoreboard_damage = float(
            player.damage
        )

        gap = (
            scoreboard_damage
            - event_damage
        )

        hits = enemy_hits[
            steam_id
        ]

        # player_hurt.dmg_health is integerized while the
        # scoreboard accumulator may preserve finer precision.
        #
        # Therefore event damage must not exceed scoreboard
        # damage, and the missing amount must stay below one
        # point per enemy hurt event.
        valid = (
            -0.01
            <= gap
            <= hits + 0.01
        )

        if not valid:
            mismatches.append(
                (
                    player.name,
                    steam_id,
                    {
                        "event_damage":
                            event_damage,
                        "scoreboard_damage":
                            scoreboard_damage,
                        "gap":
                            gap,
                        "enemy_hits":
                            hits,
                    },
                )
            )

    return mismatches


def validate_demo(
    demo_path: Path,
) -> bool:
    print()
    print(
        "=" * 110
    )
    print(
        demo_path.name
    )

    demo_parser = DemoParser(
        str(demo_path)
    )

    try:
        match = demo_parser.parse()

    except Exception as exc:
        print(
            f"ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return False

    rounds = build_round_contexts(
        demo_parser.raw_parser
    )

    if not rounds:
        print(
            "FAIL: no confirmed rounds"
        )
        return False

    kda_mismatches = validate_kda_hs(
        demo_parser,
        match,
        rounds,
    )

    damage_mismatches = validate_damage(
        demo_parser,
        match,
        rounds,
    )

    print(
        f"Map:      {match.map_name}"
    )
    print(
        f"Score:    "
        f"{match.score_ct}:"
        f"{match.score_t}"
    )
    print(
        f"Rounds:   "
        f"{match.rounds_played}"
    )

    if kda_mismatches:
        print(
            "K/D/A/HS: FAIL"
        )

        for mismatch in kda_mismatches:
            print(
                "  ",
                mismatch,
            )
    else:
        print(
            "K/D/A/HS: PASS"
        )

    if damage_mismatches:
        print(
            "Damage:   FAIL"
        )

        for mismatch in damage_mismatches:
            print(
                "  ",
                mismatch,
            )
    else:
        print(
            "Damage:   PASS"
        )

    passed = (
        not kda_mismatches
        and not damage_mismatches
    )

    print(
        "Status:   "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    return passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify scoreboard "
            "K/D/A/HS and damage against "
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
    print(
        "=" * 110
    )
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

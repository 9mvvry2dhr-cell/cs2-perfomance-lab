from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.round_context import build_round_contexts, find_round, safe_float, safe_int
from src.metrics.splits import calculate_split_metrics
from src.parsing.demo_parser import DemoParser


METRICS = (
    "rounds_played",
    "kills",
    "deaths",
    "survived_rounds",
    "kast_rounds",
    "damage",
    "entry_kills",
    "entry_deaths",
)


def normalize_sid(value) -> str | None:
    try:
        if value is None or value != value:
            return None
        return str(int(value))
    except Exception:
        value = str(value)
        return value if value else None


def blank_bucket() -> dict[str, float]:
    return {
        "rounds_played": 0,
        "kills": 0,
        "deaths": 0,
        "survived_rounds": 0,
        "kast_rounds": 0,
        "damage": 0.0,
        "entry_kills": 0,
        "entry_deaths": 0,
    }


def independent_side_map(raw_parser, rounds, player_ids):
    ticks = [round_data.freeze_end_tick for round_data in rounds]
    snapshots = raw_parser.parse_ticks(["team_num"], ticks=ticks)
    if snapshots is None or snapshots.empty:
        raise RuntimeError("No freeze-end roster snapshots")

    round_by_tick = {
        round_data.freeze_end_tick: round_data.round_num
        for round_data in rounds
    }
    side_by_round_player = {}

    for _, row in snapshots.iterrows():
        round_num = round_by_tick.get(safe_int(row.get("tick"), -1))
        steam_id = normalize_sid(row.get("steamid"))
        team_num = safe_int(row.get("team_num"), 0)
        if round_num is None or steam_id not in player_ids:
            continue
        if team_num == 2:
            side = "T"
        elif team_num == 3:
            side = "CT"
        else:
            continue
        side_by_round_player[(round_num, steam_id)] = side

    return side_by_round_player


def independent_team_state(raw_parser, ticks):
    if not ticks:
        return {}
    snapshots = raw_parser.parse_ticks(["team_num"], ticks=sorted(set(ticks)))
    if snapshots is None or snapshots.empty:
        return {}

    teams = {}
    for _, row in snapshots.iterrows():
        steam_id = normalize_sid(row.get("steamid"))
        if steam_id is None:
            continue
        teams[(safe_int(row.get("tick"), -1), steam_id)] = safe_int(
            row.get("team_num"), 0
        )
    return teams


def build_expected(demo_parser, match, rounds):
    raw = demo_parser.raw_parser
    player_ids = {str(player.steam_id) for player in match.players}
    expected = {
        steam_id: {"CT": blank_bucket(), "T": blank_bucket()}
        for steam_id in player_ids
    }

    side_map = independent_side_map(raw, rounds, player_ids)

    for (round_num, steam_id), side in side_map.items():
        expected[steam_id][side]["rounds_played"] += 1

    # Survival, KAST and entry occurrence are independently trust-checked
    # by their dedicated validators. Here we independently verify that the
    # product attributes those verified player-round events to the right side.
    for event in demo_parser.survival_events:
        side = side_map.get((event.round_num, str(event.steam_id)))
        if side in {"CT", "T"} and str(event.steam_id) in expected:
            expected[str(event.steam_id)][side]["survived_rounds"] += 1

    for event in demo_parser.kast_events:
        side = side_map.get((event.round_num, str(event.steam_id)))
        if side in {"CT", "T"} and str(event.steam_id) in expected:
            expected[str(event.steam_id)][side]["kast_rounds"] += 1

    for event in demo_parser.entry_events:
        attacker = str(event.attacker)
        victim = str(event.victim)
        attacker_side = side_map.get((event.round_num, attacker))
        victim_side = side_map.get((event.round_num, victim))
        if attacker in expected and attacker_side in {"CT", "T"}:
            expected[attacker][attacker_side]["entry_kills"] += 1
        if victim in expected and victim_side in {"CT", "T"}:
            expected[victim][victim_side]["entry_deaths"] += 1

    deaths = raw.parse_event("player_death")
    if deaths is None or deaths.empty:
        raise RuntimeError("No player_death events")

    deaths = deaths.copy()
    deaths["_event_order"] = range(len(deaths))
    deaths = deaths.sort_values(["tick", "_event_order"], kind="stable")

    match_start_tick = rounds[0].start_tick
    match_end_tick = rounds[-1].end_tick

    death_ticks = [
        safe_int(row.get("tick"), -1)
        for _, row in deaths.iterrows()
        if (
            match_start_tick
            <= safe_int(row.get("tick"), -1)
            <= match_end_tick
        )
    ]
    teams = independent_team_state(raw, death_ticks)

    for _, row in deaths.iterrows():
        tick = safe_int(row.get("tick"), -1)
        if tick < match_start_tick or tick > match_end_tick:
            continue

        round_context = find_round(tick, rounds)
        attacker = normalize_sid(row.get("attacker_steamid"))
        victim = normalize_sid(row.get("user_steamid"))

        if victim in expected:
            victim_team = teams.get((tick, victim), 0)

            if victim_team == 2:
                victim_side = "T"
            elif victim_team == 3:
                victim_side = "CT"
            elif round_context is not None:
                victim_side = side_map.get(
                    (round_context.round_num, victim)
                )
            else:
                victim_side = None

            if victim_side in {"CT", "T"}:
                expected[victim][victim_side]["deaths"] += 1

        if attacker is None or victim is None or attacker == victim:
            continue

        attacker_team = teams.get((tick, attacker), 0)
        victim_team = teams.get((tick, victim), 0)
        if (
            attacker_team not in {2, 3}
            or victim_team not in {2, 3}
            or attacker_team == victim_team
        ):
            continue

        side = "T" if attacker_team == 2 else "CT"
        if attacker in expected:
            expected[attacker][side]["kills"] += 1

    end_ticks = [round_data.end_tick for round_data in rounds]
    damage_df = raw.parse_ticks(["damage_total"], ticks=end_ticks)
    if damage_df is None or damage_df.empty:
        raise RuntimeError("No round-end damage snapshots")

    damage_by_tick_player = {}
    for _, row in damage_df.iterrows():
        steam_id = normalize_sid(row.get("steamid"))
        if steam_id not in expected:
            continue
        damage_by_tick_player[(safe_int(row.get("tick"), -1), steam_id)] = safe_float(
            row.get("damage_total"), 0.0
        )

    for steam_id in sorted(player_ids):
        previous = 0.0
        continuity_valid = True
        for round_data in rounds:
            current = damage_by_tick_player.get((round_data.end_tick, steam_id))
            if current is None:
                continuity_valid = False
                continue
            if not continuity_valid:
                previous = current
                continuity_valid = True
                continue
            delta = current - previous
            previous = current
            if delta < 0:
                continue
            side = side_map.get((round_data.round_num, steam_id))
            if side in {"CT", "T"}:
                expected[steam_id][side]["damage"] += delta

    return expected


def compare(expected, actual):
    mismatches = []
    for steam_id, sides in expected.items():
        for side in ("CT", "T"):
            actual_side = actual.get(steam_id, {}).get(side, {})
            for metric in METRICS:
                want = sides[side][metric]
                got = actual_side.get(metric, 0.0 if metric == "damage" else 0)
                if metric == "damage":
                    equal = abs(float(want) - float(got)) <= 0.01
                else:
                    equal = int(want) == int(got)
                if not equal:
                    mismatches.append((steam_id, side, metric, want, got))
    return mismatches


def overall_invariants(match, actual):
    errors = []
    count_fields = (
        "rounds_played",
        "kills",
        "deaths",
        "survived_rounds",
        "kast_rounds",
        "entry_kills",
        "entry_deaths",
    )

    for player in match.players:
        steam_id = str(player.steam_id)
        sides = actual.get(steam_id, {})
        for field in count_fields:
            split_total = sum(
                int(sides.get(side, {}).get(field, 0)) for side in ("CT", "T")
            )
            overall = int(getattr(player, field))
            if split_total != overall:
                errors.append((steam_id, field, split_total, overall))

        split_damage = sum(
            float(sides.get(side, {}).get("damage", 0.0)) for side in ("CT", "T")
        )
        if abs(split_damage - float(player.damage)) > 0.11:
            errors.append((steam_id, "damage", split_damage, float(player.damage)))

    return errors


def validate_demo(demo_path: Path) -> bool:
    print()
    print("=" * 110)
    print(demo_path.name)

    demo_parser = DemoParser(str(demo_path))

    try:
        match = demo_parser.parse()
        rounds = build_round_contexts(demo_parser.raw_parser)
        if not rounds:
            print("CT/T:      FAIL - no confirmed rounds")
            return False

        player_ids = [str(player.steam_id) for player in match.players]
        actual = calculate_split_metrics(
            demo_parser.raw_parser,
            player_ids,
            side_events=demo_parser.side_events,
            survival_events=demo_parser.survival_events,
            kast_events=demo_parser.kast_events,
            entry_events=demo_parser.entry_events,
        )
        expected = build_expected(demo_parser, match, rounds)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return False

    mismatches = compare(expected, actual)
    invariant_errors = overall_invariants(match, actual)

    print(f"Map:       {match.map_name}")
    print(f"Score:     {match.score_ct}:{match.score_t}")
    print(f"Rounds:    {match.rounds_played}")

    if mismatches or invariant_errors:
        print("CT/T:      FAIL")
        for item in mismatches:
            print("  mismatch:", item)
        for item in invariant_errors:
            print("  invariant:", item)
        return False

    print("CT/T:      PASS")
    print("Status:    PASS")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify CT/T split attribution for rounds, kills, deaths, damage, "
            "survival, KAST and entry metrics."
        )
    )
    parser.add_argument("demo_dir", type=Path)
    args = parser.parse_args()

    if not args.demo_dir.exists():
        print(f"Directory not found: {args.demo_dir}")
        return 2

    demo_files = sorted(args.demo_dir.glob("*.dem"))
    if not demo_files:
        print(f"No .dem files found in {args.demo_dir}")
        return 2

    print(f"Found demos: {len(demo_files)}")
    passed = sum(validate_demo(path) for path in demo_files)
    failed = len(demo_files) - passed

    print()
    print("=" * 110)
    print(f"RESULT: {passed} passed / {failed} failed / {len(demo_files)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.round_context import build_round_contexts, find_round, safe_int
from src.metrics.splits import calculate_split_metrics
from src.metrics.team_context import build_team_state, team_relation
from src.parsing.demo_parser import DemoParser


def normalize_sid(value) -> str | None:
    try:
        if value is None or value != value:
            return None
        return str(int(value))
    except Exception:
        value = str(value)
        return value if value else None


def build_normalized_teams(raw_parser, ticks):
    snapshots = raw_parser.parse_ticks(["team_num"], ticks=sorted(set(ticks)))
    result = {}
    if snapshots is None or snapshots.empty:
        return result

    for _, row in snapshots.iterrows():
        sid = normalize_sid(row.get("steamid"))
        if sid is None:
            continue
        result[(safe_int(row.get("tick"), -1), sid)] = safe_int(
            row.get("team_num"), 0
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose CT/T split K/D mismatches event by event."
    )
    parser.add_argument("demo_file", type=Path)
    args = parser.parse_args()

    if not args.demo_file.is_file():
        print(f"File not found: {args.demo_file}")
        return 2

    demo = DemoParser(str(args.demo_file))

    try:
        match = demo.parse()
        rounds = build_round_contexts(demo.raw_parser)
        player_ids = [str(player.steam_id) for player in match.players]
        split = calculate_split_metrics(
            demo.raw_parser,
            player_ids,
            side_events=demo.side_events,
            survival_events=demo.survival_events,
            kast_events=demo.kast_events,
            entry_events=demo.entry_events,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    names = {str(player.steam_id): player.name for player in match.players}
    overall = {
        str(player.steam_id): {
            "kills": int(player.kills),
            "deaths": int(player.deaths),
        }
        for player in match.players
    }

    mismatched = {}
    for sid in player_ids:
        split_kills = sum(int(split[sid][side]["kills"]) for side in ("CT", "T"))
        split_deaths = sum(int(split[sid][side]["deaths"]) for side in ("CT", "T"))
        if (
            split_kills != overall[sid]["kills"]
            or split_deaths != overall[sid]["deaths"]
        ):
            mismatched[sid] = {
                "overall_kills": overall[sid]["kills"],
                "split_kills": split_kills,
                "overall_deaths": overall[sid]["deaths"],
                "split_deaths": split_deaths,
            }

    print("=" * 110)
    print(args.demo_file.name)
    print(f"Map:       {match.map_name}")
    print(f"Score:     {match.score_ct}:{match.score_t}")
    print(f"Rounds:    {match.rounds_played}")
    print()

    if not mismatched:
        print("No K/D split mismatches.")
        return 0

    print("MISMATCHED PLAYERS")
    for sid, data in mismatched.items():
        print(
            f"  {names.get(sid, 'Unknown')!r} {sid}: "
            f"K {data['split_kills']}/{data['overall_kills']}  "
            f"D {data['split_deaths']}/{data['overall_deaths']}"
        )

    deaths = demo.raw_parser.parse_event("player_death")
    deaths = deaths.copy()
    deaths["_event_order"] = range(len(deaths))
    deaths = deaths.sort_values(["tick", "_event_order"], kind="stable")

    match_start = rounds[0].start_tick
    match_end = rounds[-1].end_tick
    official = deaths[
        (deaths["tick"] >= match_start)
        & (deaths["tick"] <= match_end)
    ].copy()

    ticks = sorted(
        official["tick"].dropna().astype(int).unique().tolist()
    )

    normalized_teams = build_normalized_teams(demo.raw_parser, ticks)
    production_teams = build_team_state(demo.raw_parser, ticks)

    side_map = {
        (event.round_num, str(event.steam_id)): event.side
        for event in (demo.side_events or [])
    }

    death_rounds = defaultdict(list)
    independent_kills = []
    production_missed_kills = []
    outside_round_events = []

    for _, row in official.iterrows():
        tick = safe_int(row.get("tick"), -1)
        round_context = find_round(tick, rounds)

        attacker_norm = normalize_sid(row.get("attacker_steamid"))
        victim_norm = normalize_sid(row.get("user_steamid"))
        attacker_raw = str(row.get("attacker_steamid", ""))
        victim_raw = str(row.get("user_steamid", ""))

        if round_context is None:
            if attacker_norm in mismatched or victim_norm in mismatched:
                outside_round_events.append(
                    {
                        "tick": tick,
                        "attacker": attacker_norm,
                        "victim": victim_norm,
                        "attacker_raw": row.get("attacker_steamid"),
                        "victim_raw": row.get("user_steamid"),
                        "attacker_team": normalized_teams.get((tick, attacker_norm), 0),
                        "victim_team": normalized_teams.get((tick, victim_norm), 0),
                        "production_attacker_team": production_teams.get(
                            (tick, str(row.get("attacker_steamid", "")))
                        ),
                        "production_victim_team": production_teams.get(
                            (tick, str(row.get("user_steamid", "")))
                        ),
                    }
                )
            continue

        round_num = round_context.round_num

        if victim_norm in mismatched:
            death_rounds[victim_norm].append(
                {
                    "round": round_num,
                    "tick": tick,
                    "raw": victim_raw,
                    "norm": victim_norm,
                    "raw_in_players": victim_raw in split,
                    "raw_side": side_map.get((round_num, victim_raw)),
                    "norm_side": side_map.get((round_num, victim_norm)),
                }
            )

        if attacker_norm is None or victim_norm is None or attacker_norm == victim_norm:
            continue

        attacker_team = normalized_teams.get((tick, attacker_norm), 0)
        victim_team = normalized_teams.get((tick, victim_norm), 0)
        independent_valid = (
            attacker_team in {2, 3}
            and victim_team in {2, 3}
            and attacker_team != victim_team
        )

        if independent_valid and attacker_norm in mismatched:
            independent_kills.append((attacker_norm, round_num, tick))
            production_valid = (
                attacker_raw in split
                and side_map.get((round_num, attacker_raw)) in {"CT", "T"}
                and team_relation(
                    production_teams,
                    tick,
                    attacker_raw,
                    victim_raw,
                ) == "enemy"
            )
            if not production_valid:
                production_missed_kills.append(
                    {
                        "sid": attacker_norm,
                        "round": round_num,
                        "tick": tick,
                        "attacker_raw": attacker_raw,
                        "victim_raw": victim_raw,
                        "attacker_raw_in_players": attacker_raw in split,
                        "side_raw": side_map.get((round_num, attacker_raw)),
                        "side_norm": side_map.get((round_num, attacker_norm)),
                        "production_relation": team_relation(
                            production_teams,
                            tick,
                            attacker_raw,
                            victim_raw,
                        ),
                    }
                )

    print()
    print("DEATH DIAGNOSTICS")
    print("-" * 110)

    for sid in mismatched:
        events = death_rounds.get(sid, [])
        by_round = Counter(item["round"] for item in events)
        print(f"{names.get(sid, 'Unknown')!r} {sid}: raw official deaths={len(events)}")
        duplicates = {rnd: count for rnd, count in by_round.items() if count > 1}
        if duplicates:
            print(f"  repeated deaths in same canonical round: {duplicates}")
        for item in events:
            suspicious = (
                not item["raw_in_players"]
                or item["raw_side"] not in {"CT", "T"}
                or by_round[item["round"]] > 1
            )
            if suspicious:
                print(
                    "  "
                    f"R{item['round']} tick={item['tick']} "
                    f"raw={item['raw']!r} norm={item['norm']!r} "
                    f"raw_in_players={item['raw_in_players']} "
                    f"raw_side={item['raw_side']} norm_side={item['norm_side']}"
                )

    print()
    print("OUTSIDE CANONICAL ROUND EVENTS")
    print("-" * 110)

    if not outside_round_events:
        print("No official kill/death events involving mismatched players outside canonical rounds.")
    else:
        for item in outside_round_events:
            print(
                f"tick={item['tick']} "
                f"attacker={names.get(item['attacker'], item['attacker'])!r} "
                f"({item['attacker']}) team={item['attacker_team']} "
                f"prod_team={item['production_attacker_team']} "
                f"raw={item['attacker_raw']!r} "
                f"type={type(item['attacker_raw']).__name__}  "
                f"victim={names.get(item['victim'], item['victim'])!r} "
                f"({item['victim']}) team={item['victim_team']} "
                f"prod_team={item['production_victim_team']} "
                f"raw={item['victim_raw']!r} "
                f"type={type(item['victim_raw']).__name__}"
            )

    print()
    print("KILL DIAGNOSTICS")
    print("-" * 110)

    if not production_missed_kills:
        print("No independently valid enemy kills missed by production split logic.")
    else:
        for item in production_missed_kills:
            print(
                f"{names.get(item['sid'], 'Unknown')!r} {item['sid']} "
                f"R{item['round']} tick={item['tick']} "
                f"attacker_raw={item['attacker_raw']!r} "
                f"victim_raw={item['victim_raw']!r} "
                f"raw_in_players={item['attacker_raw_in_players']} "
                f"side_raw={item['side_raw']} side_norm={item['side_norm']} "
                f"relation={item['production_relation']}"
            )

    print()
    print(
        "Interpretation: repeated deaths point to the one-death-per-round cap; "
        "raw/norm differences point to SteamID normalization; "
        "relation=unknown points to team-state lookup."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

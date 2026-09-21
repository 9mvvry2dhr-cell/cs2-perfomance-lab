from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.round_context import build_round_contexts, find_round, safe_int
from src.parsing.demo_parser import DemoParser


def normalize_sid(value) -> str | None:
    try:
        if value is None or value != value:
            return None
        return str(int(value))
    except Exception:
        value = str(value)
        return value if value else None


def side_name(team_num: int) -> str:
    if team_num == 2:
        return "T"
    if team_num == 3:
        return "CT"
    return "?"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose missing CT/T side attribution for kill/death events."
    )
    parser.add_argument("demo_file", type=Path)
    args = parser.parse_args()

    demo_file = args.demo_file
    if not demo_file.is_file():
        print(f"File not found: {demo_file}")
        return 2

    demo = DemoParser(str(demo_file))

    try:
        match = demo.parse()
        rounds = build_round_contexts(demo.raw_parser)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    side_map = {
        (event.round_num, str(event.steam_id)): event.side
        for event in (demo.side_events or [])
    }

    player_ids = {str(player.steam_id) for player in match.players}
    names = {str(player.steam_id): player.name for player in match.players}

    deaths = demo.raw_parser.parse_event("player_death")
    if deaths is None or deaths.empty:
        print("No player_death events")
        return 1

    deaths = deaths.copy()
    deaths["_event_order"] = range(len(deaths))
    deaths = deaths.sort_values(["tick", "_event_order"], kind="stable")

    event_ticks = sorted({
        safe_int(row.get("tick"), -1)
        for _, row in deaths.iterrows()
        if find_round(row.get("tick"), rounds) is not None
    })

    team_df = demo.raw_parser.parse_ticks(["team_num"], ticks=event_ticks)
    teams = {}

    if team_df is not None and not team_df.empty:
        for _, row in team_df.iterrows():
            sid = normalize_sid(row.get("steamid"))
            if sid is None:
                continue
            teams[(safe_int(row.get("tick"), -1), sid)] = safe_int(
                row.get("team_num"), 0
            )

    gaps = []

    for _, row in deaths.iterrows():
        tick = safe_int(row.get("tick"), -1)
        round_context = find_round(tick, rounds)
        if round_context is None:
            continue

        round_num = round_context.round_num
        attacker = normalize_sid(row.get("attacker_steamid"))
        victim = normalize_sid(row.get("user_steamid"))

        for role, sid in (("KILLER", attacker), ("VICTIM", victim)):
            if sid is None or sid not in player_ids:
                continue

            freeze_side = side_map.get((round_num, sid))
            if freeze_side in {"CT", "T"}:
                continue

            event_team = teams.get((tick, sid), 0)
            gaps.append(
                (
                    round_num,
                    tick,
                    role,
                    sid,
                    names.get(sid, "Unknown"),
                    side_name(event_team),
                )
            )

    print("=" * 100)
    print(demo_file.name)
    print(f"Map:       {match.map_name}")
    print(f"Score:     {match.score_ct}:{match.score_t}")
    print(f"Rounds:    {match.rounds_played}")
    print()

    if not gaps:
        print("No kill/death events with missing freeze-end side attribution.")
        return 0

    print("EVENTS WITH MISSING FREEZE-END SIDE")
    print("-" * 100)

    for round_num, tick, role, sid, name, event_side in gaps:
        print(
            f"R{round_num:<2} tick={tick:<8} "
            f"{role:<6} sid={sid} "
            f"name={name!r} event_side={event_side}"
        )

    print()
    print(
        "If event_side is CT/T while freeze-end side is missing, "
        "the split layer is dropping a real mid-round/reconnect event."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

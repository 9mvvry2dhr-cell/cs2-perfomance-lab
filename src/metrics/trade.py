from typing import Dict, List, Tuple

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_float,
    safe_int,
    valid_sid,
)
from src.metrics.team_context import (
    build_team_state,
    team_relation,
)


TRADE_WINDOW_SECONDS = 5.0


def calculate_trade_metrics(
    parser: RawDemoParser,
    player_steam_ids: List[str],
    trade_window_seconds: float = TRADE_WINDOW_SECONDS,
) -> Tuple[
    Dict[str, int],
    Dict[str, int],
]:
    """
    Calculate confirmed trade kills and traded deaths.

    A death is traded when:

    - player A is killed by enemy X;
    - in the same round;
    - within the configured time window;
    - a teammate of A kills X.

    The retaliation kill is counted as one trade kill even if it
    trades more than one recent teammate death.
    """

    trade_kills = {
        str(steam_id): 0
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    traded_deaths = {
        str(steam_id): 0
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    if trade_window_seconds < 0:
        return (
            trade_kills,
            traded_deaths,
        )

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return (
            trade_kills,
            traded_deaths,
        )

    try:
        death_events = parser.parse_event(
            "player_death",
            other=["game_time"],
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception:
        return (
            trade_kills,
            traded_deaths,
        )

    required_columns = {
        "tick",
        "game_time",
        "attacker_steamid",
        "user_steamid",
    }

    if (
        df_deaths is None
        or not hasattr(df_deaths, "empty")
        or df_deaths.empty
        or not required_columns.issubset(
            df_deaths.columns
        )
    ):
        return (
            trade_kills,
            traded_deaths,
        )

    df_deaths = df_deaths.copy()

    df_deaths["_event_order"] = range(
        len(df_deaths)
    )

    df_deaths = df_deaths.sort_values(
        [
            "tick",
            "_event_order",
        ],
        kind="stable",
    )

    death_ticks = [
        safe_int(
            tick,
            default=-1,
        )
        for tick in df_deaths["tick"]
    ]

    team_state = build_team_state(
        parser,
        death_ticks,
    )

    # Only confirmed enemy kills are allowed to participate
    # in trade detection.
    kills = []

    for _, row in df_deaths.iterrows():

        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        game_time = safe_float(
            row.get("game_time"),
            default=-1.0,
        )

        attacker = str(
            row.get(
                "attacker_steamid",
                "",
            )
        )

        victim = str(
            row.get(
                "user_steamid",
                "",
            )
        )

        if (
            tick < 0
            or game_time < 0
            or not valid_sid(attacker)
            or not valid_sid(victim)
        ):
            continue

        round_context = find_round(
            tick,
            rounds,
        )

        if round_context is None:
            continue

        if (
            team_relation(
                team_state,
                tick,
                attacker,
                victim,
            )
            != "enemy"
        ):
            # Ignore suicide, teamkill, and unknown relation.
            continue

        kills.append({
            "event_order": safe_int(
                row.get("_event_order"),
                default=-1,
            ),
            "round_num":
                round_context.round_num,
            "tick": tick,
            "game_time": game_time,
            "attacker": attacker,
            "victim": victim,
        })

    trade_kill_events = set()

    for index, death in enumerate(kills):

        dead_player = death[
            "victim"
        ]

        killer = death[
            "attacker"
        ]

        dead_player_team = team_state.get(
            (
                death["tick"],
                dead_player,
            )
        )

        if dead_player_team not in {
            2,
            3,
        }:
            continue

        for retaliation in kills[
            index + 1:
        ]:

            if (
                retaliation["round_num"]
                != death["round_num"]
            ):
                # Events are sorted by tick, therefore once
                # the next round begins this death cannot
                # be traded anymore.
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

            if elapsed > trade_window_seconds:
                break

            # The original killer must be the victim
            # of the retaliation kill.
            if (
                retaliation["victim"]
                != killer
            ):
                continue

            trader = retaliation[
                "attacker"
            ]

            trader_team = team_state.get(
                (
                    retaliation["tick"],
                    trader,
                )
            )

            # The retaliation must come from the same
            # team as the originally killed player.
            if (
                trader_team
                != dead_player_team
            ):
                continue

            if dead_player in traded_deaths:
                traded_deaths[
                    dead_player
                ] += 1

            trade_kill_events.add(
                retaliation[
                    "event_order"
                ]
            )

            break

    # One retaliation kill is one trade kill, even if
    # several teammate deaths are covered by it.
    for kill in kills:

        if (
            kill["event_order"]
            not in trade_kill_events
        ):
            continue

        trader = kill[
            "attacker"
        ]

        if trader in trade_kills:
            trade_kills[
                trader
            ] += 1

    return (
        trade_kills,
        traded_deaths,
    )

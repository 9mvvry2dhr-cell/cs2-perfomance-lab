from dataclasses import dataclass
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


@dataclass(frozen=True)
class TradeEvent:
    round_num: int

    victim: str
    trader: str
    original_killer: str

    death_tick: int
    retaliation_tick: int

    death_game_time: float
    retaliation_game_time: float

    retaliation_event_order: int


def detect_trade_events(
    parser: RawDemoParser,
    trade_window_seconds: float = TRADE_WINDOW_SECONDS,
) -> List[TradeEvent]:
    """
    Return confirmed round-level trade events.

    One TradeEvent represents one traded death.

    A single retaliation kill may therefore produce multiple
    TradeEvent objects when it trades multiple recent teammate deaths.
    """

    if trade_window_seconds < 0:
        return []

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return []

    try:
        death_events = parser.parse_event(
            "player_death",
            other=["game_time"],
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception:
        return []

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
        return []

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

    confirmed_enemy_kills = []

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
            # Suicide, teamkill and unknown relation
            # cannot participate in a confirmed trade.
            continue

        confirmed_enemy_kills.append({
            "event_order": safe_int(
                row.get("_event_order"),
                default=-1,
            ),
            "round_num": round_context.round_num,
            "tick": tick,
            "game_time": game_time,
            "attacker": attacker,
            "victim": victim,
        })

    trade_events: List[TradeEvent] = []

    for index, death in enumerate(
        confirmed_enemy_kills
    ):

        dead_player = death[
            "victim"
        ]

        original_killer = death[
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

        for retaliation in confirmed_enemy_kills[
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

            if elapsed > trade_window_seconds:
                break

            # The original killer must die in the retaliation.
            if (
                retaliation["victim"]
                != original_killer
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

            # Trader must belong to the original victim's team.
            if (
                trader_team
                != dead_player_team
            ):
                continue

            trade_events.append(
                TradeEvent(
                    round_num=death[
                        "round_num"
                    ],
                    victim=dead_player,
                    trader=trader,
                    original_killer=original_killer,
                    death_tick=death[
                        "tick"
                    ],
                    retaliation_tick=retaliation[
                        "tick"
                    ],
                    death_game_time=death[
                        "game_time"
                    ],
                    retaliation_game_time=retaliation[
                        "game_time"
                    ],
                    retaliation_event_order=retaliation[
                        "event_order"
                    ],
                )
            )

            # First confirmed valid retaliation closes this death.
            break

    return trade_events


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

    trade_kills:
        number of distinct retaliation kills made by a player.

    traded_deaths:
        number of the player's deaths successfully traded.

    One retaliation kill can trade multiple teammate deaths,
    but it is still only one trade kill.
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

    trade_events = detect_trade_events(
        parser,
        trade_window_seconds=trade_window_seconds,
    )

    retaliation_events = set()

    for event in trade_events:

        if event.victim in traded_deaths:
            traded_deaths[
                event.victim
            ] += 1

        retaliation_key = (
            event.retaliation_event_order,
            event.retaliation_tick,
            event.trader,
            event.original_killer,
        )

        if retaliation_key in retaliation_events:
            continue

        retaliation_events.add(
            retaliation_key
        )

        if event.trader in trade_kills:
            trade_kills[
                event.trader
            ] += 1

    return (
        trade_kills,
        traded_deaths,
    )

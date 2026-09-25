from dataclasses import dataclass
import math
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

# Internal CS2Lab heuristic.
# A player has a trade opportunity when a teammate dies to an enemy
# while the player is alive and within this distance of the killer.
# We deliberately keep this conservative and expose the definition
# in the UI instead of presenting it as a universal CS2 standard.
TRADE_OPPORTUNITY_DISTANCE = 900.0


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


def calculate_trade_opportunities(
    parser: RawDemoParser,
    player_steam_ids: List[str],
    max_distance: float = TRADE_OPPORTUNITY_DISTANCE,
) -> Dict[str, int]:
    """
    Estimate player-specific trade opportunities.

    Opportunity definition:
    - a teammate is killed by an enemy;
    - the candidate player is alive at that death tick;
    - the candidate is on the victim's team;
    - the candidate is within max_distance game units of the killer.

    Confirmed trade events are always included for the trader, even
    when a position snapshot is unavailable. This guarantees that a
    verified successful trade cannot exist without at least one
    corresponding opportunity.
    """

    opportunities = {
        str(steam_id): 0
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    if max_distance <= 0:
        return opportunities

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return opportunities

    try:
        death_events = parser.parse_event(
            "player_death",
            other=["game_time"],
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception:
        return opportunities

    required_columns = {
        "tick",
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
        return opportunities

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

    death_ticks = sorted({
        safe_int(
            tick,
            default=-1,
        )
        for tick in df_deaths["tick"]
        if safe_int(
            tick,
            default=-1,
        ) >= 0
    })

    try:
        df_state = parser.parse_ticks(
            [
                "team_num",
                "health",
                "X",
                "Y",
                "Z",
            ],
            ticks=death_ticks,
        )

    except Exception:
        df_state = None

    state = {}

    state_columns = {
        "tick",
        "steamid",
        "team_num",
        "health",
        "X",
        "Y",
        "Z",
    }

    if (
        df_state is not None
        and hasattr(df_state, "empty")
        and not df_state.empty
        and state_columns.issubset(
            df_state.columns
        )
    ):
        for _, row in df_state.iterrows():

            tick = safe_int(
                row.get("tick"),
                default=-1,
            )

            steam_id = str(
                row.get(
                    "steamid",
                    "",
                )
            )

            if (
                tick < 0
                or not valid_sid(
                    steam_id
                )
            ):
                continue

            x = safe_float(
                row.get("X"),
                default=float("nan"),
            )

            y = safe_float(
                row.get("Y"),
                default=float("nan"),
            )

            z = safe_float(
                row.get("Z"),
                default=float("nan"),
            )

            if not all(
                math.isfinite(value)
                for value in (
                    x,
                    y,
                    z,
                )
            ):
                continue

            state[
                (
                    tick,
                    steam_id,
                )
            ] = {
                "team_num": safe_int(
                    row.get("team_num"),
                    default=-1,
                ),
                "health": safe_int(
                    row.get("health"),
                    default=0,
                ),
                "x": x,
                "y": y,
                "z": z,
            }

    opportunity_keys = set()

    for _, row in df_deaths.iterrows():

        tick = safe_int(
            row.get("tick"),
            default=-1,
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

        attacker_state = state.get(
            (
                tick,
                attacker,
            )
        )

        victim_state = state.get(
            (
                tick,
                victim,
            )
        )

        if (
            attacker_state is None
            or victim_state is None
        ):
            continue

        attacker_team = attacker_state[
            "team_num"
        ]

        victim_team = victim_state[
            "team_num"
        ]

        if (
            attacker_team not in {2, 3}
            or victim_team not in {2, 3}
            or attacker_team == victim_team
        ):
            continue

        for player in opportunities:

            if player == victim:
                continue

            player_state = state.get(
                (
                    tick,
                    player,
                )
            )

            if player_state is None:
                continue

            if (
                player_state["team_num"]
                != victim_team
                or player_state["health"]
                <= 0
            ):
                continue

            distance = math.dist(
                (
                    player_state["x"],
                    player_state["y"],
                    player_state["z"],
                ),
                (
                    attacker_state["x"],
                    attacker_state["y"],
                    attacker_state["z"],
                ),
            )

            if distance > max_distance:
                continue

            opportunity_keys.add(
                (
                    round_context.round_num,
                    tick,
                    victim,
                    player,
                )
            )

    # A confirmed trade is definitive evidence that the trader had
    # a real opportunity, so include it even if the positional
    # snapshot was missing or outside the heuristic radius.
    for event in detect_trade_events(
        parser
    ):
        if event.trader not in opportunities:
            continue

        opportunity_keys.add(
            (
                event.round_num,
                event.death_tick,
                event.victim,
                event.trader,
            )
        )

    for (
        _,
        _,
        _,
        player,
    ) in opportunity_keys:
        opportunities[
            player
        ] += 1

    return opportunities


def calculate_trade_metrics_v2(
    parser: RawDemoParser,
    player_steam_ids: List[str],
    trade_window_seconds: float = TRADE_WINDOW_SECONDS,
    opportunity_distance: float = TRADE_OPPORTUNITY_DISTANCE,
) -> Tuple[
    Dict[str, int],
    Dict[str, int],
    Dict[str, int],
]:
    """
    Return:
        trade_opportunities,
        trade_kills,
        traded_deaths.

    The old calculate_trade_metrics() contract is kept below for
    compatibility with existing callers and tests.
    """

    (
        trade_kills,
        traded_deaths,
    ) = calculate_trade_metrics(
        parser,
        player_steam_ids,
        trade_window_seconds=trade_window_seconds,
    )

    trade_opportunities = (
        calculate_trade_opportunities(
            parser,
            player_steam_ids,
            max_distance=opportunity_distance,
        )
    )

    # Defensive invariant: a successful trade must never yield a
    # conversion above 100% because of missing position snapshots.
    for player, trade_kill_count in trade_kills.items():
        trade_opportunities[
            player
        ] = max(
            trade_opportunities.get(
                player,
                0,
            ),
            trade_kill_count,
        )

    return (
        trade_opportunities,
        trade_kills,
        traded_deaths,
    )


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

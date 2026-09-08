from typing import Dict, Iterable, Tuple

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    safe_int,
    valid_sid,
)


TeamState = Dict[
    Tuple[int, str],
    int,
]


def build_team_state(
    raw_parser: RawDemoParser,
    ticks: Iterable[int],
) -> TeamState:
    """
    Возвращает team_num игроков на конкретных ticks.

    Формат:

        {
            (tick, steam_id): team_num
        }

    Source team_num:
        T  = 2
        CT = 3
    """

    normalized_ticks = sorted({
        safe_int(
            tick,
            default=-1,
        )
        for tick in ticks
        if safe_int(
            tick,
            default=-1,
        ) >= 0
    })

    if not normalized_ticks:
        return {}

    try:
        df_teams = raw_parser.parse_ticks(
            ["team_num"],
            ticks=normalized_ticks,
        )

    except Exception:
        return {}

    if (
        df_teams is None
        or not hasattr(df_teams, "empty")
        or df_teams.empty
        or "steamid" not in df_teams.columns
        or "team_num" not in df_teams.columns
    ):
        return {}

    team_state: TeamState = {}

    for _, row in df_teams.iterrows():

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

        if not valid_sid(steam_id):
            continue

        team_state[
            (
                tick,
                steam_id,
            )
        ] = safe_int(
            row.get(
                "team_num",
                -1,
            ),
            default=-1,
        )

    return team_state


def team_relation(
    team_state: TeamState,
    tick,
    first_player,
    second_player,
) -> str:
    """
    Определяет отношение двух игроков на конкретном tick.

    Возвращает:
        enemy
        teammate
        self
        unknown
    """

    tick = safe_int(
        tick,
        default=-1,
    )

    first_player = str(
        first_player
    )

    second_player = str(
        second_player
    )

    if (
        not valid_sid(first_player)
        or not valid_sid(second_player)
    ):
        return "unknown"

    if first_player == second_player:
        return "self"

    first_team = team_state.get(
        (
            tick,
            first_player,
        )
    )

    second_team = team_state.get(
        (
            tick,
            second_player,
        )
    )

    if (
        first_team not in {2, 3}
        or second_team not in {2, 3}
    ):
        return "unknown"

    if first_team == second_team:
        return "teammate"

    return "enemy"
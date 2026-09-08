from dataclasses import dataclass
from typing import Dict, List

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_int,
    valid_sid,
)


@dataclass(frozen=True)
class SurvivalRound:
    """
    One verified player survival in one confirmed round.
    """

    round_num: int
    steam_id: str


def detect_survival_rounds(
    parser: RawDemoParser,
    player_steam_ids: List[str],
) -> List[SurvivalRound]:
    """
    Detect verified surviving player-rounds.

    Rules:
    - player must be present in the valid freeze_end roster;
    - player must have a valid CT/T team_num;
    - any player_death event where the player is the victim
      removes survival for that round;
    - enemy kill, teamkill and suicide all break survival;
    - round assignment uses shared round_context;
    - no fixed-round assumptions.
    """

    player_ids = {
        str(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    if not player_ids:
        return []

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return []

    # --------------------------------------------------------------
    # Freeze-end rosters
    # --------------------------------------------------------------

    snapshot_ticks = [
        round_data.freeze_end_tick
        for round_data in rounds
    ]

    try:
        df_rosters = parser.parse_ticks(
            ["team_num"],
            ticks=snapshot_ticks,
        )

    except Exception:
        return []

    if (
        df_rosters is None
        or not hasattr(df_rosters, "empty")
        or df_rosters.empty
        or "steamid" not in df_rosters.columns
        or "team_num" not in df_rosters.columns
        or "tick" not in df_rosters.columns
    ):
        return []

    round_by_snapshot_tick = {
        round_data.freeze_end_tick:
        round_data.round_num
        for round_data in rounds
    }

    roster_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    for _, row in df_rosters.iterrows():

        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_num = round_by_snapshot_tick.get(
            tick
        )

        if round_num is None:
            continue

        steam_id = str(
            row.get(
                "steamid",
                "",
            )
        )

        if (
            steam_id not in player_ids
            or not valid_sid(steam_id)
        ):
            continue

        team_num = safe_int(
            row.get(
                "team_num",
                -1,
            ),
            default=-1,
        )

        if team_num not in {2, 3}:
            continue

        roster_by_round[
            round_num
        ].add(
            steam_id
        )

    # --------------------------------------------------------------
    # Deaths
    # --------------------------------------------------------------

    try:
        death_events = parser.parse_events(
            ["player_death"]
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception:
        return []

    if (
        df_deaths is None
        or not hasattr(df_deaths, "empty")
    ):
        return []

    dead_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    if not df_deaths.empty:

        required_columns = {
            "tick",
            "user_steamid",
        }

        if not required_columns.issubset(
            df_deaths.columns
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

        for _, row in df_deaths.iterrows():

            tick = safe_int(
                row.get("tick"),
                default=-1,
            )

            if tick < 0:
                continue

            round_context = find_round(
                tick,
                rounds,
            )

            if round_context is None:
                continue

            round_num = (
                round_context.round_num
            )

            victim = str(
                row.get(
                    "user_steamid",
                    "",
                )
            )

            if (
                not valid_sid(victim)
                or victim
                not in roster_by_round[
                    round_num
                ]
            ):
                continue

            dead_by_round[
                round_num
            ].add(
                victim
            )

    # --------------------------------------------------------------
    # Survivors
    # --------------------------------------------------------------

    results = []

    for round_data in rounds:

        round_num = round_data.round_num

        survivors = (
            roster_by_round[
                round_num
            ]
            - dead_by_round[
                round_num
            ]
        )

        for steam_id in sorted(
            survivors
        ):
            results.append(
                SurvivalRound(
                    round_num=round_num,
                    steam_id=steam_id,
                )
            )

    return results


def calculate_survival_metrics(
    parser: RawDemoParser,
    player_steam_ids: List[str],
) -> Dict[str, int]:
    """
    Calculate verified survived-round counts.
    """

    player_ids = {
        str(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    survived_rounds = {
        steam_id: 0
        for steam_id in player_ids
    }

    if not player_ids:
        return survived_rounds

    for event in detect_survival_rounds(
        parser,
        list(player_ids),
    ):
        if event.steam_id in survived_rounds:
            survived_rounds[
                event.steam_id
            ] += 1

    return survived_rounds

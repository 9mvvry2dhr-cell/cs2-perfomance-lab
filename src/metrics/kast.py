from typing import Dict, List

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_int,
    valid_sid,
)
from src.metrics.team_context import (
    build_team_state,
    team_relation,
)
from src.metrics.trade import detect_trade_events


def calculate_kast_metrics(
    parser: RawDemoParser,
    player_steam_ids: List[str],
) -> Dict[str, int]:
    """
    Calculate KAST-positive rounds for each player.

    A round is KAST-positive when the player has at least one:

    K - confirmed enemy kill
    A - confirmed assist on an enemy kill
    S - survived the round
    T - their death was traded

    Each round counts at most once per player.
    """

    player_ids = {
        str(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    kast_rounds = {
        steam_id: 0
        for steam_id in player_ids
    }

    if not player_ids:
        return kast_rounds

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return kast_rounds

    # --------------------------------------------------------------
    # Round rosters at freeze_end
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
        return kast_rounds

    if (
        df_rosters is None
        or not hasattr(df_rosters, "empty")
        or df_rosters.empty
        or "steamid" not in df_rosters.columns
        or "team_num" not in df_rosters.columns
        or "tick" not in df_rosters.columns
    ):
        return kast_rounds

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
    # Death events
    # --------------------------------------------------------------

    try:
        death_events = parser.parse_events(
            ["player_death"]
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception:
        return kast_rounds

    if (
        df_deaths is None
        or not hasattr(df_deaths, "empty")
    ):
        return kast_rounds

    positive_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    dead_by_round = {
        round_data.round_num: set()
        for round_data in rounds
    }

    if not df_deaths.empty:

        required_columns = {
            "tick",
            "attacker_steamid",
            "user_steamid",
        }

        if not required_columns.issubset(
            df_deaths.columns
        ):
            return kast_rounds

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

            round_num = round_context.round_num

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

            assister = str(
                row.get(
                    "assister_steamid",
                    "",
                )
            )

            # S: any real death removes survival.
            if (
                valid_sid(victim)
                and victim in roster_by_round[
                    round_num
                ]
            ):
                dead_by_round[
                    round_num
                ].add(
                    victim
                )

            # K: only confirmed enemy kills.
            relation = team_relation(
                team_state,
                tick,
                attacker,
                victim,
            )

            if relation != "enemy":
                continue

            if (
                attacker in player_ids
                and attacker in roster_by_round[
                    round_num
                ]
            ):
                positive_by_round[
                    round_num
                ].add(
                    attacker
                )

            # A: credited assister must be an enemy
            # of the victim on the exact kill tick.
            if (
                valid_sid(assister)
                and assister in player_ids
                and assister in roster_by_round[
                    round_num
                ]
                and team_relation(
                    team_state,
                    tick,
                    assister,
                    victim,
                )
                == "enemy"
            ):
                positive_by_round[
                    round_num
                ].add(
                    assister
                )

    # --------------------------------------------------------------
    # T: confirmed traded deaths
    # --------------------------------------------------------------

    trade_events = detect_trade_events(
        parser
    )

    for event in trade_events:

        if (
            event.round_num
            not in positive_by_round
            or event.victim not in player_ids
            or event.victim not in roster_by_round[
                event.round_num
            ]
        ):
            continue

        positive_by_round[
            event.round_num
        ].add(
            event.victim
        )

    # --------------------------------------------------------------
    # S: surviving roster players are KAST-positive
    # --------------------------------------------------------------

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

        positive_by_round[
            round_num
        ].update(
            survivors
        )

    # --------------------------------------------------------------
    # Final count
    # --------------------------------------------------------------

    for round_data in rounds:

        round_num = round_data.round_num

        for steam_id in positive_by_round[
            round_num
        ]:

            if steam_id in kast_rounds:
                kast_rounds[
                    steam_id
                ] += 1

    return kast_rounds

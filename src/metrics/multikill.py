from collections import defaultdict
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
from src.metrics.team_context import (
    build_team_state,
    team_relation,
)


@dataclass(frozen=True)
class MultikillRound:
    """
    One player's confirmed enemy kills in one round.

    Only rounds with at least two confirmed enemy kills
    are exposed as multikill rounds.
    """

    round_num: int
    steam_id: str
    kills: int


def detect_multikill_rounds(
    parser: RawDemoParser,
) -> List[MultikillRound]:
    """
    Detect verified multikill rounds.

    Rules:
    - only player_death events inside confirmed rounds;
    - attacker and victim must be valid SteamIDs;
    - attacker must be a confirmed enemy of the victim
      on the exact kill tick;
    - teamkills, suicides and unknown team relation
      do not count;
    - one MultikillRound is emitted when a player has
      at least two confirmed enemy kills in that round.
    """

    rounds = build_round_contexts(parser)

    if not rounds:
        return []

    try:
        events = parser.parse_events(
            ["player_death"]
        )
        df_deaths = extract_dataframe(
            events
        )

    except Exception:
        return []

    if (
        df_deaths is None
        or not hasattr(df_deaths, "empty")
        or df_deaths.empty
    ):
        return []

    required_columns = {
        "tick",
        "attacker_steamid",
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

    kills_by_round_player = defaultdict(
        int
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
            not valid_sid(attacker)
            or not valid_sid(victim)
        ):
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
            continue

        kills_by_round_player[
            (
                round_context.round_num,
                attacker,
            )
        ] += 1

    results = []

    for (
        round_num,
        steam_id,
    ), kills in sorted(
        kills_by_round_player.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
        ),
    ):
        if kills < 2:
            continue

        results.append(
            MultikillRound(
                round_num=round_num,
                steam_id=steam_id,
                kills=kills,
            )
        )

    return results


def calculate_multikill_metrics(
    parser: RawDemoParser,
    player_steam_ids: List[str],
) -> Dict[str, Dict[str, int]]:
    """
    Calculate exact 2K / 3K / 4K / 5K round counts.

    Categories are exclusive:
    - a 2K round increments only two_k_rounds;
    - a 3K round increments only three_k_rounds;
    - etc.
    """

    player_ids = {
        str(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    metrics = {
        steam_id: {
            "two_k_rounds": 0,
            "three_k_rounds": 0,
            "four_k_rounds": 0,
            "five_k_rounds": 0,
        }
        for steam_id in player_ids
    }

    if not player_ids:
        return metrics

    for event in detect_multikill_rounds(
        parser
    ):
        if event.steam_id not in metrics:
            continue

        if event.kills == 2:
            metrics[
                event.steam_id
            ][
                "two_k_rounds"
            ] += 1

        elif event.kills == 3:
            metrics[
                event.steam_id
            ][
                "three_k_rounds"
            ] += 1

        elif event.kills == 4:
            metrics[
                event.steam_id
            ][
                "four_k_rounds"
            ] += 1

        elif event.kills == 5:
            metrics[
                event.steam_id
            ][
                "five_k_rounds"
            ] += 1

    return metrics

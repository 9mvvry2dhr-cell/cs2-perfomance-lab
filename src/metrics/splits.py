from dataclasses import dataclass
from typing import List

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
from src.metrics.survival import (
    detect_survival_rounds,
)
from src.metrics.kast import (
    detect_kast_rounds,
)
from src.metrics.entry import (
    detect_entry_events,
)


@dataclass(frozen=True)
class PlayerRoundSide:
    """
    One verified player's side in one confirmed round.
    """

    round_num: int
    steam_id: str
    side: str


def detect_player_round_sides(
    parser: RawDemoParser,
    player_steam_ids: List[str],
) -> List[PlayerRoundSide]:
    """
    Detect each player's CT/T side per confirmed round.

    Rules:
    - player must exist in the freeze_end roster;
    - team_num 2 = T;
    - team_num 3 = CT;
    - unknown / invalid team values are ignored;
    - side is resolved independently for every round;
    - no halftime or fixed-round assumptions.
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
        or "tick" not in df_rosters.columns
        or "steamid" not in df_rosters.columns
        or "team_num" not in df_rosters.columns
    ):
        return []

    round_by_tick = {
        round_data.freeze_end_tick:
        round_data.round_num
        for round_data in rounds
    }

    detected = set()

    for _, row in df_rosters.iterrows():

        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_num = round_by_tick.get(
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

        if team_num == 2:
            side = "T"
        elif team_num == 3:
            side = "CT"
        else:
            continue

        detected.add(
            (
                round_num,
                steam_id,
                side,
            )
        )

    return [
        PlayerRoundSide(
            round_num=round_num,
            steam_id=steam_id,
            side=side,
        )
        for (
            round_num,
            steam_id,
            side,
        ) in sorted(
            detected,
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
        )
    ]



@dataclass(frozen=True)
class PlayerRoundDamage:
    """
    Verified scoreboard damage gained in one confirmed round.
    """

    round_num: int
    steam_id: str
    damage: float


def detect_player_round_damage(
    parser: RawDemoParser,
    player_steam_ids: List[str],
) -> List[PlayerRoundDamage]:
    """
    Detect per-round damage using cumulative scoreboard damage_total.

    Damage for a round is:

        current round_end damage_total
        - previous round_end damage_total

    This avoids player_hurt overkill inflation.

    Fail closed:
    - missing snapshot breaks continuity for that player;
    - negative delta means counter reset and breaks continuity;
    - no combined multi-round delta is attributed to one round.
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

    end_ticks = [
        round_data.end_tick
        for round_data in rounds
    ]

    try:
        df_damage = parser.parse_ticks(
            ["damage_total"],
            ticks=end_ticks,
        )

    except Exception:
        return []

    if (
        df_damage is None
        or not hasattr(df_damage, "empty")
        or df_damage.empty
        or "tick" not in df_damage.columns
        or "steamid" not in df_damage.columns
        or "damage_total" not in df_damage.columns
    ):
        return []

    damage_by_tick_player = {}

    for _, row in df_damage.iterrows():

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
            or steam_id not in player_ids
            or not valid_sid(steam_id)
        ):
            continue

        damage_by_tick_player[
            (
                tick,
                steam_id,
            )
        ] = safe_float(
            row.get(
                "damage_total",
                0.0,
            ),
            default=0.0,
        )

    results = []

    for steam_id in sorted(
        player_ids
    ):

        previous = 0.0
        continuity_valid = True

        for round_data in rounds:

            current = damage_by_tick_player.get(
                (
                    round_data.end_tick,
                    steam_id,
                )
            )

            if current is None:
                continuity_valid = False
                continue

            if not continuity_valid:
                previous = current
                continuity_valid = True
                continue

            delta = (
                current
                - previous
            )

            if delta < 0:
                previous = current
                continue

            results.append(
                PlayerRoundDamage(
                    round_num=round_data.round_num,
                    steam_id=steam_id,
                    damage=delta,
                )
            )

            previous = current

    return results


def calculate_split_metrics(
    parser: RawDemoParser,
    player_steam_ids: List[str],
):
    """
    Calculate verified CT/T split counts.

    Current metrics:
    - rounds_played
    - kills
    - deaths
    - survived_rounds
    - kast_rounds
    - damage

    Side is resolved from the player's freeze_end roster
    independently for every confirmed round.
    """

    player_ids = {
        str(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    metrics = {
        steam_id: {
            "CT": {
                "rounds_played": 0,
                "kills": 0,
                "deaths": 0,
                "survived_rounds": 0,
                "kast_rounds": 0,
                "damage": 0.0,
                "entry_kills": 0,
                "entry_deaths": 0,
            },
            "T": {
                "rounds_played": 0,
                "kills": 0,
                "deaths": 0,
                "survived_rounds": 0,
                "kast_rounds": 0,
                "damage": 0.0,
                "entry_kills": 0,
                "entry_deaths": 0,
            },
        }
        for steam_id in player_ids
    }

    if not player_ids:
        return metrics

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return metrics

    side_events = detect_player_round_sides(
        parser,
        list(player_ids),
    )

    side_by_round_player = {
        (
            event.round_num,
            event.steam_id,
        ): event.side
        for event in side_events
    }

    # --------------------------------------------------------------
    # Rounds played
    # --------------------------------------------------------------

    for event in side_events:
        metrics[
            event.steam_id
        ][
            event.side
        ][
            "rounds_played"
        ] += 1

    # --------------------------------------------------------------
    # Survival
    # --------------------------------------------------------------

    survival_events = detect_survival_rounds(
        parser,
        list(player_ids),
    )

    for event in survival_events:

        side = side_by_round_player.get(
            (
                event.round_num,
                event.steam_id,
            )
        )

        if side not in {"CT", "T"}:
            continue

        metrics[
            event.steam_id
        ][
            side
        ][
            "survived_rounds"
        ] += 1

    # --------------------------------------------------------------
    # KAST
    # --------------------------------------------------------------

    kast_events = detect_kast_rounds(
        parser,
        list(player_ids),
    )

    for event in kast_events:

        side = side_by_round_player.get(
            (
                event.round_num,
                event.steam_id,
            )
        )

        if side not in {"CT", "T"}:
            continue

        metrics[
            event.steam_id
        ][
            side
        ][
            "kast_rounds"
        ] += 1

    # --------------------------------------------------------------
    # Damage
    # --------------------------------------------------------------

    damage_events = detect_player_round_damage(
        parser,
        list(player_ids),
    )

    for event in damage_events:

        side = side_by_round_player.get(
            (
                event.round_num,
                event.steam_id,
            )
        )

        if side not in {"CT", "T"}:
            continue

        metrics[
            event.steam_id
        ][
            side
        ][
            "damage"
        ] += event.damage

    # --------------------------------------------------------------
    # Entry
    # --------------------------------------------------------------

    entry_events = detect_entry_events(
        parser
    )

    for event in entry_events:

        attacker_side = side_by_round_player.get(
            (
                event.round_num,
                event.attacker,
            )
        )

        if (
            event.attacker in metrics
            and attacker_side in {"CT", "T"}
        ):
            metrics[
                event.attacker
            ][
                attacker_side
            ][
                "entry_kills"
            ] += 1

        victim_side = side_by_round_player.get(
            (
                event.round_num,
                event.victim,
            )
        )

        if (
            event.victim in metrics
            and victim_side in {"CT", "T"}
        ):
            metrics[
                event.victim
            ][
                victim_side
            ][
                "entry_deaths"
            ] += 1

    # --------------------------------------------------------------
    # Death events
    # --------------------------------------------------------------

    try:
        events = parser.parse_events(
            ["player_death"]
        )

        df_deaths = extract_dataframe(
            events
        )

    except Exception:
        return metrics

    if (
        df_deaths is None
        or not hasattr(df_deaths, "empty")
        or df_deaths.empty
    ):
        return metrics

    required_columns = {
        "tick",
        "attacker_steamid",
        "user_steamid",
    }

    if not required_columns.issubset(
        df_deaths.columns
    ):
        return metrics

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

    dead_player_rounds = set()

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

        # ----------------------------------------------------------
        # Death
        #
        # Any real death breaks survival and counts as a death,
        # including teamkill or suicide.
        # Count at most one death per player-round.
        # ----------------------------------------------------------

        victim_side = (
            side_by_round_player.get(
                (
                    round_num,
                    victim,
                )
            )
        )

        death_key = (
            round_num,
            victim,
        )

        if (
            valid_sid(victim)
            and victim in metrics
            and victim_side in {"CT", "T"}
            and death_key
            not in dead_player_rounds
        ):
            metrics[
                victim
            ][
                victim_side
            ][
                "deaths"
            ] += 1

            dead_player_rounds.add(
                death_key
            )

        # ----------------------------------------------------------
        # Kill
        #
        # Only confirmed enemy kills count.
        # ----------------------------------------------------------

        attacker_side = (
            side_by_round_player.get(
                (
                    round_num,
                    attacker,
                )
            )
        )

        if (
            attacker not in metrics
            or attacker_side not in {"CT", "T"}
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

        metrics[
            attacker
        ][
            attacker_side
        ][
            "kills"
        ] += 1

    return metrics

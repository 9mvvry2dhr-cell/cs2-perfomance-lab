from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from src.metrics.round_context import (
    RoundContext,
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_int,
    valid_sid,
)


CONTACT_GAP_TICKS = 320
CLOSE_LOSS_HP_MAX = 30

EXCLUDED_WEAPONS = {
    "knife",
    "knife_t",
    "hegrenade",
    "inferno",
    "molotov",
    "flashbang",
    "smokegrenade",
    "decoy",
    "taser",
    "world",
    "c4",
}


def _empty_metrics() -> dict[str, int | float | None]:
    return {
        "combat_outcomes": 0,
        "gun_kills": 0,
        "gun_deaths": 0,
        "clean_wins": 0,
        "contested_duels": 0,
        "contested_wins": 0,
        "contested_losses": 0,
        "contested_win_rate": None,
        "no_return_losses": 0,
        "non_instant_no_return_losses": 0,
        "instant_losses": 0,
        "lost_after_first_damage": 0,
        "close_losses": 0,
        "first_damage_wins": 0,
        "first_damage_losses": 0,
    }


def _sid(value: Any) -> str:
    return str(value)


def _excluded_weapon(value: Any) -> bool:
    weapon = str(value or "").strip().lower()

    if weapon.startswith("knife"):
        return True

    return weapon in EXCLUDED_WEAPONS


def _build_team_map(
    parser,
    rounds: list[RoundContext],
) -> dict[tuple[int, str], int]:
    """
    Build verified team membership for every player at round start.

    Used to reject teamkills/self damage from duel metrics.
    """

    if not rounds:
        return {}

    snapshot_ticks = [
        round_data.freeze_end_tick
        for round_data in rounds
    ]

    try:
        df = parser.parse_ticks(
            ["team_num"],
            ticks=snapshot_ticks,
        )
    except Exception:
        return {}

    if (
        df is None
        or not hasattr(df, "empty")
        or df.empty
        or "tick" not in df.columns
        or "steamid" not in df.columns
        or "team_num" not in df.columns
    ):
        return {}

    round_by_tick = {
        round_data.freeze_end_tick:
        round_data.round_num
        for round_data in rounds
    }

    result: dict[
        tuple[int, str],
        int,
    ] = {}

    for _, row in df.iterrows():
        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_num = round_by_tick.get(
            tick
        )

        if round_num is None:
            continue

        steam_id = _sid(
            row.get("steamid", "")
        )

        if not valid_sid(steam_id):
            continue

        team_num = safe_int(
            row.get("team_num"),
            default=-1,
        )

        if team_num not in {2, 3}:
            continue

        result[
            (
                round_num,
                steam_id,
            )
        ] = team_num

    return result


def calculate_duel_metrics_from_events(
    *,
    hurt,
    deaths,
    rounds: list[RoundContext],
    player_steam_ids: Iterable[str],
    team_by_round_player: Mapping[
        tuple[int, str],
        int,
    ],
    contact_gap_ticks: int = (
        CONTACT_GAP_TICKS
    ),
) -> dict[
    str,
    dict[str, int | float | None],
]:
    """
    Calculate verified gunfight outcome metrics.

    This layer does not decide whether the player performed
    well or badly. It only records combat facts.

    The same metrics are used for wins and losses.
    """

    player_ids = {
        _sid(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    }

    metrics = {
        steam_id: _empty_metrics()
        for steam_id in player_ids
    }

    if not player_ids:
        return metrics

    if (
        hurt is None
        or deaths is None
        or not hasattr(hurt, "empty")
        or not hasattr(deaths, "empty")
        or hurt.empty
        or deaths.empty
    ):
        return metrics

    required_hurt = {
        "tick",
        "attacker_steamid",
        "user_steamid",
        "health",
    }

    required_deaths = {
        "tick",
        "attacker_steamid",
        "user_steamid",
        "weapon",
    }

    if (
        not required_hurt.issubset(
            hurt.columns
        )
        or not required_deaths.issubset(
            deaths.columns
        )
    ):
        return metrics

    hurt = hurt.copy()
    deaths = deaths.copy()

    hurt["_attacker_sid"] = (
        hurt["attacker_steamid"]
        .astype(str)
    )

    hurt["_victim_sid"] = (
        hurt["user_steamid"]
        .astype(str)
    )

    deaths["_attacker_sid"] = (
        deaths["attacker_steamid"]
        .astype(str)
    )

    deaths["_victim_sid"] = (
        deaths["user_steamid"]
        .astype(str)
    )

    deaths = deaths.sort_values(
        "tick",
        kind="stable",
    )

    for self_sid in sorted(player_ids):
        player_events = deaths[
            (
                deaths["_attacker_sid"]
                == self_sid
            )
            |
            (
                deaths["_victim_sid"]
                == self_sid
            )
        ]

        for _, death in (
            player_events.iterrows()
        ):
            attacker = death[
                "_attacker_sid"
            ]

            victim = death[
                "_victim_sid"
            ]

            if attacker == self_sid:
                outcome = "WIN"
                opponent = victim

            elif victim == self_sid:
                outcome = "LOSS"
                opponent = attacker

            else:
                continue

            if (
                not valid_sid(opponent)
                or opponent == self_sid
            ):
                continue

            weapon = death.get(
                "weapon",
                "",
            )

            if _excluded_weapon(weapon):
                continue

            death_tick = safe_int(
                death.get("tick"),
                default=-1,
            )

            round_context = find_round(
                death_tick,
                rounds,
            )

            if round_context is None:
                continue

            round_num = (
                round_context.round_num
            )

            self_team = (
                team_by_round_player.get(
                    (
                        round_num,
                        self_sid,
                    )
                )
            )

            opponent_team = (
                team_by_round_player.get(
                    (
                        round_num,
                        opponent,
                    )
                )
            )

            # Fail closed: count only verified enemies.
            if (
                self_team not in {2, 3}
                or opponent_team
                not in {2, 3}
                or self_team == opponent_team
            ):
                continue

            pair = hurt[
                (
                    (
                        hurt["_attacker_sid"]
                        == self_sid
                    )
                    &
                    (
                        hurt["_victim_sid"]
                        == opponent
                    )
                )
                |
                (
                    (
                        hurt["_attacker_sid"]
                        == opponent
                    )
                    &
                    (
                        hurt["_victim_sid"]
                        == self_sid
                    )
                )
            ]

            pair = pair[
                (
                    pair["tick"]
                    >= round_context.start_tick
                )
                &
                (
                    pair["tick"]
                    <= death_tick
                )
            ].sort_values(
                "tick",
                kind="stable",
            )

            rows = list(
                pair.to_dict(
                    "records"
                )
            )

            contact = []
            last_tick = death_tick

            for row in reversed(rows):
                tick = safe_int(
                    row.get("tick"),
                    default=-1,
                )

                if (
                    last_tick - tick
                    > contact_gap_ticks
                ):
                    break

                contact.append(row)
                last_tick = tick

            contact.reverse()

            self_hits = [
                row
                for row in contact
                if (
                    row["_attacker_sid"]
                    == self_sid
                    and
                    row["_victim_sid"]
                    == opponent
                )
            ]

            enemy_hits = [
                row
                for row in contact
                if (
                    row["_attacker_sid"]
                    == opponent
                    and
                    row["_victim_sid"]
                    == self_sid
                )
            ]

            # The lethal side must have verified hurt data.
            if (
                outcome == "WIN"
                and not self_hits
            ):
                continue

            if (
                outcome == "LOSS"
                and not enemy_hits
            ):
                continue

            first_damage = (
                "YOU"
                if (
                    contact
                    and contact[0][
                        "_attacker_sid"
                    ]
                    == self_sid
                )
                else "ENEMY"
            )

            reciprocal = bool(
                self_hits
                and enemy_hits
            )

            instant_loss = (
                outcome == "LOSS"
                and not self_hits
                and len(enemy_hits) == 1
            )

            opponent_hp = (
                safe_int(
                    self_hits[-1].get(
                        "health"
                    ),
                    default=-1,
                )
                if self_hits
                else None
            )

            current = metrics[
                self_sid
            ]

            current[
                "combat_outcomes"
            ] += 1

            if outcome == "WIN":
                current[
                    "gun_kills"
                ] += 1

                if reciprocal:
                    current[
                        "contested_duels"
                    ] += 1

                    current[
                        "contested_wins"
                    ] += 1

                else:
                    current[
                        "clean_wins"
                    ] += 1

                if (
                    first_damage == "YOU"
                ):
                    current[
                        "first_damage_wins"
                    ] += 1

            else:
                current[
                    "gun_deaths"
                ] += 1

                if reciprocal:
                    current[
                        "contested_duels"
                    ] += 1

                    current[
                        "contested_losses"
                    ] += 1

                    if (
                        first_damage
                        == "YOU"
                    ):
                        current[
                            "lost_after_first_damage"
                        ] += 1

                        current[
                            "first_damage_losses"
                        ] += 1

                    if (
                        opponent_hp
                        is not None
                        and opponent_hp >= 0
                        and opponent_hp
                        <= CLOSE_LOSS_HP_MAX
                    ):
                        current[
                            "close_losses"
                        ] += 1

                else:
                    current[
                        "no_return_losses"
                    ] += 1

                    if instant_loss:
                        current[
                            "instant_losses"
                        ] += 1
                    else:
                        current[
                            "non_instant_no_return_losses"
                        ] += 1

        contested = int(
            metrics[self_sid][
                "contested_duels"
            ]
        )

        contested_wins = int(
            metrics[self_sid][
                "contested_wins"
            ]
        )

        metrics[self_sid][
            "contested_win_rate"
        ] = (
            round(
                contested_wins
                / contested
                * 100,
                1,
            )
            if contested > 0
            else None
        )

    return metrics


def calculate_duel_metrics(
    parser,
    player_steam_ids: Iterable[str],
) -> dict[
    str,
    dict[str, int | float | None],
]:
    """
    Parse raw demo events and calculate duel metrics.

    Fail-closed by design:
    if combat/team context cannot be verified,
    no duel claim is produced.
    """

    player_ids = [
        _sid(steam_id)
        for steam_id in player_steam_ids
        if valid_sid(steam_id)
    ]

    empty = {
        steam_id: _empty_metrics()
        for steam_id in player_ids
    }

    if not player_ids:
        return empty

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return empty

    try:
        hurt = extract_dataframe(
            parser.parse_events(
                ["player_hurt"]
            )
        )

        deaths = extract_dataframe(
            parser.parse_events(
                ["player_death"]
            )
        )
    except Exception:
        return empty

    team_by_round_player = (
        _build_team_map(
            parser,
            rounds,
        )
    )

    if not team_by_round_player:
        return empty

    return calculate_duel_metrics_from_events(
        hurt=hurt,
        deaths=deaths,
        rounds=rounds,
        player_steam_ids=player_ids,
        team_by_round_player=(
            team_by_round_player
        ),
    )
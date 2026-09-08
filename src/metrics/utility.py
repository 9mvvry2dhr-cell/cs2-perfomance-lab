from collections import defaultdict

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    find_round,
)

from src.metrics.team_context import (
    build_team_state,
    team_relation,
)


UTILITY_WEAPONS = {
    "hegrenade": "he",
    "inferno": "fire",
    "molotov": "fire",
    "incgrenade": "fire",
}


def calculate_utility_metrics(
    raw_parser: RawDemoParser
) -> dict:
    """
    Возвращает Utility-статистику по SteamID:

    {
        "steamid": {
            "he_damage": float,
            "inferno_damage": float,
            "enemies_flashed": int,
            "flash_duration": float,
        }
    }

    Data Trust правила:

    1. Учитываем только события внутри сыгранных раундов.
    2. Utility damage считается только по врагам.
    3. Self/team damage не учитывается.
    4. Overkill damage обрезается до HP жертвы перед попаданием.
    5. Flash считается только если ослеплён враг.
    6. Self/team flash не учитывается.
    """

    stats = {}

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _init_player(steam_id):
        steam_id = str(steam_id)

        if not _valid_sid(steam_id):
            return

        if steam_id not in stats:
            stats[steam_id] = {
                "he_damage": 0.0,
                "inferno_damage": 0.0,
                "enemies_flashed": 0,
                "flash_duration": 0.0,
            }

    # ------------------------------------------------------------------
    # SHARED ROUND CONTEXT
    # ------------------------------------------------------------------

    rounds = build_round_contexts(
        raw_parser
    )

    if not rounds:
        return stats

    def _assign_round(tick):
        round_context = find_round(
            tick,
            rounds,
        )

        if round_context is None:
            return None

        return round_context.round_num

    # ------------------------------------------------------------------
    # EVENTS
    # ------------------------------------------------------------------

    try:
        hurt_events = raw_parser.parse_events(
            ["player_hurt"]
        )

        df_hurt = _extract_dataframe(
            hurt_events
        )

    except Exception as exc:
        print(
            f"⚠️ Ошибка при парсинге player_hurt: {exc}"
        )
        df_hurt = None

    try:
        blind_events = raw_parser.parse_events(
            ["player_blind"]
        )

        df_blind = _extract_dataframe(
            blind_events
        )

    except Exception as exc:
        print(
            f"⚠️ Ошибка при парсинге player_blind: {exc}"
        )
        df_blind = None

    # ------------------------------------------------------------------
    # Все ticks, где нам понадобится team_num.
    # ------------------------------------------------------------------

    event_ticks = set()

    if (
        df_hurt is not None
        and not df_hurt.empty
        and "tick" in df_hurt.columns
    ):
        for _, row in df_hurt.iterrows():

            weapon = str(
                row.get(
                    "weapon",
                    ""
                )
            ).lower()

            if weapon not in UTILITY_WEAPONS:
                continue

            tick = _safe_int(
                row.get("tick"),
                default=-1
            )

            if _assign_round(tick) is not None:
                event_ticks.add(tick)

    if (
        df_blind is not None
        and not df_blind.empty
        and "tick" in df_blind.columns
    ):
        for _, row in df_blind.iterrows():

            tick = _safe_int(
                row.get("tick"),
                default=-1
            )

            if _assign_round(tick) is not None:
                event_ticks.add(tick)

    # ------------------------------------------------------------------
    # SHARED TEAM CONTEXT
    #
    # ???????? ??????? ??????? ??????????????? ?? ticks ???????.
    # ??????? halftime / overtime ??????????? ?????????????.
    # ------------------------------------------------------------------

    team_at_tick = build_team_state(
        raw_parser,
        event_ticks,
    )

    # ==================================================================
    # UTILITY DAMAGE
    # ==================================================================

    # HP после предыдущего player_hurt.
    #
    # Ключ содержит round_num, поэтому состояние автоматически
    # сбрасывается в начале каждого нового раунда.
    health_state = {}

    if (
        df_hurt is not None
        and not df_hurt.empty
    ):
        df_hurt = df_hurt.copy()

        # Сохраняем исходный порядок событий с одинаковым tick.
        df_hurt["_event_order"] = range(
            len(df_hurt)
        )

        df_hurt = df_hurt.sort_values(
            [
                "tick",
                "_event_order",
            ],
            kind="stable"
        )

        for _, row in df_hurt.iterrows():

            tick = _safe_int(
                row.get("tick"),
                default=-1
            )

            round_num = _assign_round(
                tick
            )

            # Не считаем warmup / post-match / другие
            # события вне подтверждённых раундов.
            if round_num is None:
                continue

            attacker = str(
                row.get(
                    "attacker_steamid",
                    ""
                )
            )

            victim = str(
                row.get(
                    "user_steamid",
                    ""
                )
            )

            raw_damage = max(
                0.0,
                _safe_float(
                    row.get(
                        "dmg_health",
                        0
                    )
                )
            )

            current_health = max(
                0.0,
                _safe_float(
                    row.get(
                        "health",
                        0
                    )
                )
            )

            # ----------------------------------------------------------
            # Восстанавливаем HP жертвы перед событием.
            # ----------------------------------------------------------

            health_key = (
                round_num,
                victim,
            )

            previous_health = health_state.get(
                health_key,
                100.0
            )

            # dmg_health может содержать overkill.
            #
            # Например:
            # у жертвы 20 HP,
            # dmg_health = 80.
            #
            # В статистику должно пойти максимум 20.
            actual_damage = min(
                raw_damage,
                max(
                    previous_health,
                    0.0
                )
            )

            # Обновляем HP после КАЖДОГО hurt event,
            # а не только utility.
            health_state[
                health_key
            ] = current_health

            weapon = str(
                row.get(
                    "weapon",
                    ""
                )
            ).lower()

            utility_type = UTILITY_WEAPONS.get(
                weapon
            )

            if utility_type is None:
                continue

            if not _valid_sid(attacker):
                continue

            # Utility damage только по врагу.
            if (
                team_relation(
                    team_at_tick,
                    tick,
                    attacker,
                    victim,
                )
                != "enemy"
            ):
                continue

            _init_player(
                attacker
            )

            if utility_type == "he":
                stats[
                    attacker
                ]["he_damage"] += actual_damage

            elif utility_type == "fire":
                stats[
                    attacker
                ]["inferno_damage"] += actual_damage

    # ==================================================================
    # FLASH
    # ==================================================================

    if (
        df_blind is not None
        and not df_blind.empty
    ):
        df_blind = df_blind.sort_values(
            "tick"
        )

        for _, row in df_blind.iterrows():

            tick = _safe_int(
                row.get("tick"),
                default=-1
            )

            # Только события внутри сыгранных раундов.
            if _assign_round(tick) is None:
                continue

            attacker = str(
                row.get(
                    "attacker_steamid",
                    ""
                )
            )

            victim = str(
                row.get(
                    "user_steamid",
                    ""
                )
            )

            duration = _safe_float(
                row.get(
                    "blind_duration",
                    0.0
                ),
                default=0.0
            )

            if (
                not _valid_sid(attacker)
                or not _valid_sid(victim)
                or duration <= 0
            ):
                continue

            # Только enemy flash.
            if (
                team_relation(
                    team_at_tick,
                    tick,
                    attacker,
                    victim,
                )
                != "enemy"
            ):
                continue

            _init_player(
                attacker
            )

            stats[
                attacker
            ]["enemies_flashed"] += 1

            stats[
                attacker
            ]["flash_duration"] += duration

    return stats


# ======================================================================
# GENERIC HELPERS
# ======================================================================

def _extract_dataframe(events):
    """
    demoparser2 может вернуть DataFrame напрямую
    либо list/tuple.
    """

    if events is None:
        return None

    if hasattr(events, "iterrows"):
        return events

    if (
        isinstance(events, list)
        and events
    ):
        first = events[0]

        if (
            isinstance(first, tuple)
            and len(first) >= 2
        ):
            return first[1]

        return first

    return None


def _valid_sid(value) -> bool:
    sid = str(value)

    return sid not in {
        "",
        "0",
        "None",
        "nan",
        "NaN",
    }


def _safe_int(
    value,
    default=0
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_float(
    value,
    default=0.0
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default
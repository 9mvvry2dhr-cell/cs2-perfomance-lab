from collections import defaultdict

from demoparser2 import DemoParser as RawDemoParser


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
    # LIVE ROUND WINDOWS
    # ------------------------------------------------------------------

    round_windows = _build_round_windows(
        raw_parser
    )

    if not round_windows:
        return stats

    def _assign_round(tick):
        tick = _safe_int(
            tick,
            default=-1
        )

        for round_num, start_tick, end_tick in round_windows:
            if (
                start_tick
                <= tick
                <= end_tick
            ):
                return round_num

        return None

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
    # TEAM STATE
    #
    # Получаем стороны игроков прямо на ticks событий.
    # Это автоматически переживает halftime / overtime.
    # ------------------------------------------------------------------

    team_at_tick = {}

    if event_ticks:
        try:
            df_teams = raw_parser.parse_ticks(
                ["team_num"],
                ticks=sorted(event_ticks)
            )

            if (
                df_teams is not None
                and not df_teams.empty
                and "steamid" in df_teams.columns
                and "team_num" in df_teams.columns
            ):
                for _, row in df_teams.iterrows():

                    tick = _safe_int(
                        row.get("tick"),
                        default=-1
                    )

                    steam_id = str(
                        row.get(
                            "steamid",
                            ""
                        )
                    )

                    if not _valid_sid(steam_id):
                        continue

                    team_at_tick[
                        (tick, steam_id)
                    ] = _safe_int(
                        row.get(
                            "team_num",
                            -1
                        ),
                        default=-1
                    )

        except Exception as exc:
            print(
                f"⚠️ Ошибка при получении team_num: {exc}"
            )

    # ------------------------------------------------------------------
    # TEAM RELATION
    # ------------------------------------------------------------------

    def _relation(
        tick,
        attacker,
        victim
    ):
        attacker = str(attacker)
        victim = str(victim)

        if (
            not _valid_sid(attacker)
            or not _valid_sid(victim)
        ):
            return "unknown"

        if attacker == victim:
            return "self"

        attacker_team = team_at_tick.get(
            (
                tick,
                attacker,
            )
        )

        victim_team = team_at_tick.get(
            (
                tick,
                victim,
            )
        )

        if (
            attacker_team not in {2, 3}
            or victim_team not in {2, 3}
        ):
            return "unknown"

        if attacker_team == victim_team:
            return "teammate"

        return "enemy"

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
                _relation(
                    tick,
                    attacker,
                    victim
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
                _relation(
                    tick,
                    attacker,
                    victim
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
# ROUND WINDOWS
# ======================================================================

def _build_round_windows(
    raw_parser: RawDemoParser
):
    """
    Строит окна сыгранных раундов:

        round_start <= event <= round_end

    Нет хардкода на 24 раунда.
    """

    try:
        start_events = raw_parser.parse_events(
            ["round_start"]
        )

        end_events = raw_parser.parse_events(
            ["round_end"]
        )

        df_start = _extract_dataframe(
            start_events
        )

        df_end = _extract_dataframe(
            end_events
        )

    except Exception as exc:
        print(
            f"⚠️ Ошибка при построении round windows: {exc}"
        )
        return []

    if (
        df_start is None
        or df_start.empty
        or "tick" not in df_start.columns
    ):
        return []

    if (
        df_end is None
        or df_end.empty
        or "tick" not in df_end.columns
    ):
        return []

    df_end = df_end.copy()

    # ------------------------------------------------------------------
    # Оставляем только настоящие CT/T round_end.
    # ------------------------------------------------------------------

    if "winner" in df_end.columns:
        df_end = df_end[
            df_end["winner"].apply(
                lambda value:
                _normalize_side(value)
                != "UNKNOWN"
            )
        ].copy()

    # ------------------------------------------------------------------
    # Официальный конец матча.
    # ------------------------------------------------------------------

    try:
        panel_events = raw_parser.parse_events(
            ["cs_win_panel_match"]
        )

        df_panel = _extract_dataframe(
            panel_events
        )

        if (
            df_panel is not None
            and not df_panel.empty
            and "tick" in df_panel.columns
        ):
            match_end_tick = _safe_int(
                df_panel["tick"].max(),
                default=-1
            )

            if match_end_tick >= 0:
                df_end = df_end[
                    df_end["tick"]
                    <= match_end_tick
                ].copy()

    except Exception:
        pass

    start_ticks = sorted(
        df_start["tick"]
        .dropna()
        .astype(int)
        .tolist()
    )

    end_ticks = sorted(
        df_end["tick"]
        .dropna()
        .astype(int)
        .tolist()
    )

    if (
        not start_ticks
        or not end_ticks
    ):
        return []

    # Для нашей текущей нормализованной demo-модели
    # один round_start соответствует одному round_end.
    count = min(
        len(start_ticks),
        len(end_ticks)
    )

    windows = []

    for index in range(count):

        start_tick = start_ticks[index]
        end_tick = end_ticks[index]

        if start_tick > end_tick:
            continue

        windows.append(
            (
                index + 1,
                start_tick,
                end_tick,
            )
        )

    return windows


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


def _normalize_side(value) -> str:
    if value is None:
        return "UNKNOWN"

    value = str(
        value
    ).strip().upper()

    if value in {
        "CT",
        "3",
        "COUNTER-TERRORIST",
        "COUNTER_TERRORIST",
    }:
        return "CT"

    if value in {
        "T",
        "2",
        "TERRORIST",
        "TERRORISTS",
    }:
        return "T"

    return "UNKNOWN"


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
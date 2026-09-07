from typing import Dict, List

from demoparser2 import DemoParser as RawDemoParser


def calculate_clutches(
    parser: RawDemoParser,
    player_steam_ids: List[str]
) -> Dict[str, int]:
    """
    Считает выигранные clutch-ситуации.

    Clutch win:
        игрок становится единственным живым игроком своей команды,
        при этом у противника остаётся минимум один живой игрок,
        после чего его команда выигрывает раунд,
        а сам clutch-player остаётся жив к round_end.

    Поддерживает:
    - 1v1 ... 1v5;
    - halftime;
    - overtime;
    - teamkill / suicide как реальные смерти;
    - отсутствие хардкода на 24 раунда.

    Возвращает:
        {
            steam_id: clutches_won
        }
    """

    clutches = {
        str(steam_id): 0
        for steam_id in player_steam_ids
        if _valid_sid(steam_id)
    }

    # ------------------------------------------------------------------
    # ROUND STRUCTURE
    # ------------------------------------------------------------------

    rounds = _build_rounds(
        parser
    )

    if not rounds:
        return clutches

    # ------------------------------------------------------------------
    # PLAYERS / TEAMS AT FREEZE END
    #
    # На freeze_end состав команды уже определён,
    # но раунд ещё только начинается.
    # ------------------------------------------------------------------

    snapshot_ticks = [
        round_data["freeze_tick"]
        for round_data in rounds
    ]

    try:
        df_teams = parser.parse_ticks(
            ["team_num"],
            ticks=snapshot_ticks
        )

    except Exception as exc:
        print(
            "⚠️ Ошибка при получении team state "
            f"для Clutch: {exc}"
        )
        return clutches

    if (
        df_teams is None
        or not hasattr(df_teams, "empty")
        or df_teams.empty
        or "steamid" not in df_teams.columns
        or "team_num" not in df_teams.columns
    ):
        return clutches

    round_by_snapshot = {
        round_data["freeze_tick"]:
        round_data["round_num"]
        for round_data in rounds
    }

    teams_by_round = {
        round_data["round_num"]: {
            2: set(),
            3: set(),
        }
        for round_data in rounds
    }

    for _, row in df_teams.iterrows():

        tick = _safe_int(
            row.get("tick"),
            default=-1
        )

        round_num = round_by_snapshot.get(
            tick
        )

        if round_num is None:
            continue

        steam_id = str(
            row.get(
                "steamid",
                ""
            )
        )

        if not _valid_sid(steam_id):
            continue

        team_num = _safe_int(
            row.get(
                "team_num",
                -1
            ),
            default=-1
        )

        if team_num not in {2, 3}:
            continue

        teams_by_round[
            round_num
        ][team_num].add(
            steam_id
        )

    # ------------------------------------------------------------------
    # PLAYER DEATH EVENTS
    # ------------------------------------------------------------------

    try:
        death_events = parser.parse_events(
            ["player_death"]
        )

        df_deaths = _extract_dataframe(
            death_events
        )

    except Exception as exc:
        print(
            f"⚠️ Ошибка при парсинге player_death "
            f"для Clutch: {exc}"
        )
        return clutches

    if (
        df_deaths is None
        or df_deaths.empty
        or "tick" not in df_deaths.columns
    ):
        return clutches

    df_deaths = df_deaths.copy()

    # Сохраняем реальный порядок death events,
    # если несколько событий имеют одинаковый tick.
    df_deaths["_event_order"] = range(
        len(df_deaths)
    )

    df_deaths = df_deaths.sort_values(
        [
            "tick",
            "_event_order",
        ],
        kind="stable"
    )

    # ------------------------------------------------------------------
    # CLUTCH PER ROUND
    # ------------------------------------------------------------------

    for round_data in rounds:

        round_num = round_data[
            "round_num"
        ]

        winner_team = round_data[
            "winner_team"
        ]

        start_tick = round_data[
            "start_tick"
        ]

        end_tick = round_data[
            "end_tick"
        ]

        if winner_team not in {2, 3}:
            continue

        # --------------------------------------------------------------
        # Начальное состояние живых игроков.
        # --------------------------------------------------------------

        alive = {
            2: set(
                teams_by_round[
                    round_num
                ][2]
            ),
            3: set(
                teams_by_round[
                    round_num
                ][3]
            ),
        }

        # Если состав одной из команд не определился,
        # такой раунд не угадываем.
        if (
            not alive[2]
            or not alive[3]
        ):
            continue

        # player -> количество врагов в момент,
        # когда игрок ВПЕРВЫЕ остался один.
        #
        # Первый момент важен:
        # 1v3 -> 1v2 -> 1v1 остаётся clutch 1v3.
        candidates = {}

        def detect_clutch_candidates():
            for team_num in (2, 3):

                enemy_team = (
                    3
                    if team_num == 2
                    else 2
                )

                if len(alive[team_num]) != 1:
                    continue

                enemy_count = len(
                    alive[enemy_team]
                )

                # 1v0 — уже не clutch situation.
                if enemy_count <= 0:
                    continue

                player = next(
                    iter(
                        alive[team_num]
                    )
                )

                if player not in candidates:
                    candidates[player] = {
                        "team_num": team_num,
                        "enemy_count": enemy_count,
                    }

        # На случай нестандартного старта раунда
        # проверяем начальное состояние тоже.
        detect_clutch_candidates()

        # --------------------------------------------------------------
        # Смерти этого раунда.
        # --------------------------------------------------------------

        round_deaths = df_deaths[
            (
                df_deaths["tick"]
                >= start_tick
            )
            & (
                df_deaths["tick"]
                <= end_tick
            )
        ]

        for _, death in round_deaths.iterrows():

            victim = str(
                death.get(
                    "user_steamid",
                    ""
                )
            )

            if not _valid_sid(victim):
                continue

            # Не важно, была это обычная смерть,
            # suicide или teamkill:
            # игрок после player_death больше не alive.
            alive[2].discard(
                victim
            )

            alive[3].discard(
                victim
            )

            detect_clutch_candidates()

        # --------------------------------------------------------------
        # Проверяем кандидатов после окончания раунда.
        # --------------------------------------------------------------

        for player, candidate in candidates.items():

            team_num = candidate[
                "team_num"
            ]

            # Команда clutch-player должна выиграть.
            if team_num != winner_team:
                continue

            # И сам clutch-player должен быть жив
            # на момент round_end.
            if player not in alive[team_num]:
                continue

            if player not in clutches:
                clutches[player] = 0

            clutches[player] += 1

    return clutches


# ======================================================================
# ROUND STRUCTURE
# ======================================================================

def _build_rounds(
    parser: RawDemoParser
):
    """
    Строит список настоящих сыгранных раундов:

        round_start
        round_freeze_end
        round_end

    Без хардкода на MR12 / 24 раунда.
    """

    try:
        start_events = parser.parse_events(
            ["round_start"]
        )

        freeze_events = parser.parse_events(
            ["round_freeze_end"]
        )

        end_events = parser.parse_events(
            ["round_end"]
        )

        df_start = _extract_dataframe(
            start_events
        )

        df_freeze = _extract_dataframe(
            freeze_events
        )

        df_end = _extract_dataframe(
            end_events
        )

    except Exception as exc:
        print(
            "⚠️ Ошибка при построении раундов "
            f"для Clutch: {exc}"
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
    # Только настоящие CT/T round_end.
    # ------------------------------------------------------------------

    if "winner" in df_end.columns:
        df_end = df_end[
            df_end["winner"].apply(
                lambda value:
                _winner_team_num(value)
                is not None
            )
        ].copy()

    # ------------------------------------------------------------------
    # Официальный конец матча.
    # ------------------------------------------------------------------

    try:
        panel_events = parser.parse_events(
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

    df_end = (
        df_end
        .sort_values("tick")
        .reset_index(drop=True)
    )

    start_ticks = sorted(
        df_start["tick"]
        .dropna()
        .astype(int)
        .tolist()
    )

    freeze_ticks = []

    if (
        df_freeze is not None
        and not df_freeze.empty
        and "tick" in df_freeze.columns
    ):
        freeze_ticks = sorted(
            df_freeze["tick"]
            .dropna()
            .astype(int)
            .tolist()
        )

    if (
        not start_ticks
        or df_end.empty
    ):
        return []

    rounds = []

    previous_end = -1

    for _, row in df_end.iterrows():

        end_tick = _safe_int(
            row.get("tick"),
            default=-1
        )

        if end_tick < 0:
            continue

        possible_starts = [
            tick
            for tick in start_ticks
            if (
                previous_end
                < tick
                <= end_tick
            )
        ]

        if not possible_starts:
            previous_end = end_tick
            continue

        start_tick = max(
            possible_starts
        )

        possible_freezes = [
            tick
            for tick in freeze_ticks
            if (
                start_tick
                <= tick
                <= end_tick
            )
        ]

        # Freeze end — лучший snapshot состава.
        #
        # Если событие почему-то отсутствует,
        # используем round_start как fallback.
        freeze_tick = (
            min(possible_freezes)
            if possible_freezes
            else start_tick
        )

        winner_team = _winner_team_num(
            row.get("winner")
        )

        rounds.append(
            {
                "round_num": len(rounds) + 1,
                "start_tick": start_tick,
                "freeze_tick": freeze_tick,
                "end_tick": end_tick,
                "winner_team": winner_team,
            }
        )

        previous_end = end_tick

    return rounds


# ======================================================================
# HELPERS
# ======================================================================

def _extract_dataframe(events):
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


def _winner_team_num(value):
    """
    Source team_num:
        T  = 2
        CT = 3
    """

    if value is None:
        return None

    value = str(
        value
    ).strip().upper()

    if value in {
        "T",
        "2",
        "TERRORIST",
        "TERRORISTS",
    }:
        return 2

    if value in {
        "CT",
        "3",
        "COUNTER-TERRORIST",
        "COUNTER_TERRORIST",
    }:
        return 3

    return None


def _valid_sid(value) -> bool:
    steam_id = str(
        value
    )

    return steam_id not in {
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
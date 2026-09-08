from typing import Dict, List

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    extract_dataframe,
    safe_int,
    valid_sid,
)


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
        if valid_sid(steam_id)
    }

    # ------------------------------------------------------------------
    # ROUND STRUCTURE
    # ------------------------------------------------------------------

    rounds = build_round_contexts(
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
        round_data.freeze_end_tick
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
        round_data.freeze_end_tick:
        round_data.round_num
        for round_data in rounds
    }

    teams_by_round = {
        round_data.round_num: {
            2: set(),
            3: set(),
        }
        for round_data in rounds
    }

    for _, row in df_teams.iterrows():

        tick = safe_int(
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

        if not valid_sid(steam_id):
            continue

        team_num = safe_int(
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

        df_deaths = extract_dataframe(
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

        round_num = round_data.round_num

        winner_team = round_data.winner_team

        start_tick = round_data.start_tick

        end_tick = round_data.end_tick

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

            if not valid_sid(victim):
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

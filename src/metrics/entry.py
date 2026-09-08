from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_int,
    valid_sid,
)


def calculate_entry_metrics(
    raw_parser: RawDemoParser
) -> dict:
    """
    Считает Entry Kill / Entry Death.

    Entry Kill:
        первый настоящий enemy kill сыгранного раунда.

    Entry Death:
        жертва этого opening kill.

    Правила Data Trust:
    - только события внутри live-round;
    - без хардкода на 24 раунда;
    - halftime / overtime поддерживаются;
    - suicide не является entry kill;
    - teamkill не является entry kill;
    - выбирается конкретное первое событие,
      а не pandas GroupBy.first();
    - структура раундов берётся из общего round_context.
    """

    stats = {}

    # ------------------------------------------------------------------
    # SHARED ROUND CONTEXT
    # ------------------------------------------------------------------

    rounds = build_round_contexts(
        raw_parser
    )

    if not rounds:
        return stats

    # ------------------------------------------------------------------
    # PLAYER DEATH
    # ------------------------------------------------------------------

    try:
        death_events = raw_parser.parse_events(
            ["player_death"]
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception as exc:
        print(
            f"⚠️ Ошибка при парсинге player_death: {exc}"
        )
        return stats

    if (
        df_deaths is None
        or df_deaths.empty
        or "tick" not in df_deaths.columns
    ):
        return stats

    df_deaths = df_deaths.copy()

    # Сохраняем исходный порядок событий.
    # Это важно, если несколько death events имеют одинаковый tick.
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

    # ------------------------------------------------------------------
    # DEATH TICKS INSIDE LIVE ROUNDS
    # ------------------------------------------------------------------

    death_ticks = sorted({
        safe_int(
            row.get("tick"),
            default=-1,
        )
        for _, row in df_deaths.iterrows()
        if find_round(
            row.get("tick"),
            rounds,
        ) is not None
    })

    if not death_ticks:
        return stats

    # ------------------------------------------------------------------
    # TEAM STATE
    #
    # Получаем team_num непосредственно на death ticks.
    # Поэтому смена сторон после halftime / overtime
    # учитывается автоматически.
    # ------------------------------------------------------------------

    try:
        df_teams = raw_parser.parse_ticks(
            ["team_num"],
            ticks=death_ticks,
        )

    except Exception as exc:
        print(
            f"⚠️ Ошибка при получении team_num для Entry: {exc}"
        )
        return stats

    if (
        df_teams is None
        or df_teams.empty
        or "steamid" not in df_teams.columns
        or "team_num" not in df_teams.columns
    ):
        return stats

    team_at_tick = {}

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

        team_at_tick[
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

    # ------------------------------------------------------------------
    # ENTRY-SPECIFIC HELPERS
    # ------------------------------------------------------------------

    def init_player(steam_id):
        steam_id = str(
            steam_id
        )

        if not valid_sid(steam_id):
            return

        if steam_id not in stats:
            stats[steam_id] = {
                "entry_kills": 0,
                "entry_deaths": 0,
            }

    def relation(
        tick,
        attacker,
        victim,
    ):
        attacker = str(
            attacker
        )

        victim = str(
            victim
        )

        if (
            not valid_sid(attacker)
            or not valid_sid(victim)
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

    # ------------------------------------------------------------------
    # OPENING KILLS
    # ------------------------------------------------------------------

    opened_rounds = set()

    # Если для потенциального PvP death мы не можем определить
    # команды, такой раунд лучше не угадывать.
    blocked_rounds = set()

    for _, row in df_deaths.iterrows():

        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_context = find_round(
            tick,
            rounds,
        )

        # Warmup / post-match / вне live round.
        if round_context is None:
            continue

        round_num = round_context.round_num

        # Entry этого раунда уже найден.
        if round_num in opened_rounds:
            continue

        # На этом раунде ранее была неоднозначность.
        if round_num in blocked_rounds:
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

        # World / отсутствующая жертва.
        if not valid_sid(victim):
            continue

        # World / отсутствующий attacker.
        if not valid_sid(attacker):
            continue

        # Suicide.
        if attacker == victim:
            continue

        event_relation = relation(
            tick,
            attacker,
            victim,
        )

        # Teamkill не является opening enemy kill.
        # Продолжаем искать первый enemy kill раунда.
        if event_relation == "teammate":
            continue

        # Если оба SteamID известны, но команда не определилась,
        # не угадываем Entry для этого раунда.
        if event_relation == "unknown":
            blocked_rounds.add(
                round_num
            )
            continue

        if event_relation != "enemy":
            continue

        # --------------------------------------------------------------
        # Нашли первый подтверждённый enemy kill раунда.
        # --------------------------------------------------------------

        init_player(
            attacker
        )

        init_player(
            victim
        )

        stats[
            attacker
        ]["entry_kills"] += 1

        stats[
            victim
        ]["entry_deaths"] += 1

        opened_rounds.add(
            round_num
        )

    if blocked_rounds:
        print(
            "⚠️ Entry не рассчитан для раундов "
            "с неизвестной team relation: "
            f"{sorted(blocked_rounds)}"
        )

    return stats
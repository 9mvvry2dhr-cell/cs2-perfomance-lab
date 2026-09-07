from demoparser2 import DemoParser as RawDemoParser


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
      а не pandas GroupBy.first().
    """

    stats = {}

    # ------------------------------------------------------------------
    # ROUND WINDOWS
    # ------------------------------------------------------------------

    round_windows = _build_round_windows(
        raw_parser
    )

    if not round_windows:
        return stats

    def assign_round(tick):
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
    # PLAYER DEATH
    # ------------------------------------------------------------------

    try:
        death_events = raw_parser.parse_events(
            ["player_death"]
        )

        df_deaths = _extract_dataframe(
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
        kind="stable"
    )

    # ------------------------------------------------------------------
    # DEATH TICKS INSIDE LIVE ROUNDS
    # ------------------------------------------------------------------

    death_ticks = sorted({
        _safe_int(
            row.get("tick"),
            default=-1
        )
        for _, row in df_deaths.iterrows()
        if assign_round(
            row.get("tick")
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
            ticks=death_ticks
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
            (
                tick,
                steam_id,
            )
        ] = _safe_int(
            row.get(
                "team_num",
                -1
            ),
            default=-1
        )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def init_player(steam_id):
        steam_id = str(
            steam_id
        )

        if not _valid_sid(steam_id):
            return

        if steam_id not in stats:
            stats[steam_id] = {
                "entry_kills": 0,
                "entry_deaths": 0,
            }

    def relation(
        tick,
        attacker,
        victim
    ):
        attacker = str(
            attacker
        )

        victim = str(
            victim
        )

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

    # ------------------------------------------------------------------
    # OPENING KILLS
    # ------------------------------------------------------------------

    opened_rounds = set()

    # Если для потенциального PvP death мы не можем определить
    # команды, такой раунд лучше не угадывать.
    blocked_rounds = set()

    for _, row in df_deaths.iterrows():

        tick = _safe_int(
            row.get("tick"),
            default=-1
        )

        round_num = assign_round(
            tick
        )

        # Warmup / post-match / вне live round.
        if round_num is None:
            continue

        # Entry этого раунда уже найден.
        if round_num in opened_rounds:
            continue

        # На этом раунде ранее была неоднозначность.
        if round_num in blocked_rounds:
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

        # World / отсутствующий attacker.
        if not _valid_sid(victim):
            continue

        if not _valid_sid(attacker):
            continue

        # Suicide.
        if attacker == victim:
            continue

        event_relation = relation(
            tick,
            attacker,
            victim
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


# ======================================================================
# ROUND WINDOWS
# ======================================================================

def _build_round_windows(
    raw_parser: RawDemoParser
):
    """
    Строит реальные окна:

        round_start <= event <= round_end

    Один window соответствует одному завершённому раунду.
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
            f"⚠️ Ошибка при построении Entry round windows: {exc}"
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
    # Только настоящие завершённые CT/T раунды.
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

    # ------------------------------------------------------------------
    # Для каждого round_end ищем последний round_start
    # после предыдущего round_end.
    #
    # Это безопаснее простого zip(start_ticks, end_ticks),
    # если когда-нибудь встретятся лишние round_start.
    # ------------------------------------------------------------------

    windows = []

    previous_end = -1

    for round_num, end_tick in enumerate(
        end_ticks,
        start=1
    ):
        possible_starts = [
            start_tick
            for start_tick in start_ticks
            if (
                previous_end
                < start_tick
                <= end_tick
            )
        ]

        if not possible_starts:
            previous_end = end_tick
            continue

        start_tick = max(
            possible_starts
        )

        windows.append(
            (
                round_num,
                start_tick,
                end_tick,
            )
        )

        previous_end = end_tick

    return windows


# ======================================================================
# GENERIC HELPERS
# ======================================================================

def _extract_dataframe(events):
    """
    demoparser2 может вернуть DataFrame напрямую
    или list/tuple.
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
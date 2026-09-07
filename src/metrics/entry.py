import pandas as pd
from demoparser2 import DemoParser as RawDemoParser


def calculate_entry_metrics(
    raw_parser: RawDemoParser
) -> dict:
    """
    Возвращает Entry-статистику по каждому steamid.

    Entry Kill:
        первая подтверждённая смерть в раунде.

    Entry Death:
        игрок, который стал первой жертвой раунда.

    Важно:
    здесь НЕТ хардкода на 24 раунда.
    """

    stats = {}

    def _init_player(sid):
        if (
            sid
            and sid not in stats
            and sid not in {"0", "None", ""}
        ):
            stats[sid] = {
                "entry_kills": 0,
                "entry_deaths": 0,
            }

    # ------------------------------------------------------------------
    # PLAYER DEATH
    # ------------------------------------------------------------------

    try:
        death_events = raw_parser.parse_events(
            ["player_death"]
        )

        df_deaths = None

        if isinstance(
            death_events,
            pd.DataFrame
        ):
            df_deaths = death_events

        elif (
            isinstance(death_events, list)
            and len(death_events) > 0
        ):
            first = death_events[0]

            if (
                isinstance(first, tuple)
                and len(first) >= 2
            ):
                df_deaths = first[1]
            else:
                df_deaths = first

    except Exception as e:
        print(
            f"⚠️ Ошибка при парсинге player_death: {e}"
        )
        return stats

    # ------------------------------------------------------------------
    # ROUND END
    # ------------------------------------------------------------------

    try:
        round_events = raw_parser.parse_events(
            ["round_end"]
        )

        df_rounds = None

        if isinstance(
            round_events,
            pd.DataFrame
        ):
            df_rounds = round_events

        elif (
            isinstance(round_events, list)
            and len(round_events) > 0
        ):
            first = round_events[0]

            if (
                isinstance(first, tuple)
                and len(first) >= 2
            ):
                df_rounds = first[1]
            else:
                df_rounds = first

    except Exception as e:
        print(
            f"⚠️ Ошибка при парсинге round_end: {e}"
        )
        df_rounds = None

    if (
        df_deaths is None
        or df_deaths.empty
    ):
        return stats

    df_deaths = df_deaths.sort_values(
        "tick"
    ).copy()

    # ------------------------------------------------------------------
    # ВАРИАНТ 1
    #
    # Если в player_death уже есть номер раунда,
    # используем его напрямую.
    # ------------------------------------------------------------------

    if (
        "round" in df_deaths.columns
        and df_deaths["round"].notna().any()
    ):
        try:
            df_deaths["calc_round"] = (
                df_deaths["round"]
                .astype("Int64")
            )

            first_deaths = (
                df_deaths
                .dropna(subset=["calc_round"])
                .groupby("calc_round", sort=True)
                .first()
            )

        except Exception:
            first_deaths = None

    else:
        first_deaths = None

    # ------------------------------------------------------------------
    # ВАРИАНТ 2
    #
    # Если номера раунда нет,
    # привязываем death events к round_end.
    # ------------------------------------------------------------------

    if first_deaths is None:

        if (
            df_rounds is None
            or df_rounds.empty
            or "tick" not in df_rounds.columns
        ):
            return stats

        df_valid_rounds = df_rounds.copy()

        # Если winner представлен цифрами или строками,
        # оставляем только реальные завершённые раунды.
        if "winner" in df_valid_rounds.columns:
            df_valid_rounds = df_valid_rounds[
                df_valid_rounds["winner"].astype(str).isin(
                    [
                        "2",
                        "3",
                        "T",
                        "CT",
                        "t",
                        "ct",
                    ]
                )
            ]

        round_ticks = sorted(
            df_valid_rounds["tick"]
            .dropna()
            .astype(int)
            .tolist()
        )

        if not round_ticks:
            return stats

        # --------------------------------------------------------------
        # НИКАКОГО:
        #
        # if len(round_ticks) > 24:
        #     round_ticks = round_ticks[-24:]
        #
        # Здесь намеренно нет лимита.
        # Овертайм должен сохраняться.
        # --------------------------------------------------------------

        def _assign_round(tick):
            for round_index, round_tick in enumerate(
                round_ticks
            ):
                if tick <= round_tick:
                    return round_index + 1

            return len(round_ticks) + 1

        df_deaths["calc_round"] = (
            df_deaths["tick"]
            .apply(_assign_round)
        )

        first_deaths = (
            df_deaths
            .groupby(
                "calc_round",
                sort=True
            )
            .first()
        )

    # ------------------------------------------------------------------
    # ИЗВЛЕКАЕМ ENTRY KILL / ENTRY DEATH
    # ------------------------------------------------------------------

    for _, row in first_deaths.iterrows():

        killer = str(
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

        # --------------------------------------------------------------
        # Entry Kill
        # --------------------------------------------------------------

        if (
            killer
            and killer not in {"0", "None"}
            and killer != victim
        ):
            _init_player(killer)

            if killer in stats:
                stats[
                    killer
                ]["entry_kills"] += 1

        # --------------------------------------------------------------
        # Entry Death
        # --------------------------------------------------------------

        if (
            victim
            and victim not in {"0", "None"}
        ):
            _init_player(victim)

            if victim in stats:
                stats[
                    victim
                ]["entry_deaths"] += 1

    return stats
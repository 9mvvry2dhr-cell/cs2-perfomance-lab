import os
from typing import List

from demoparser2 import DemoParser as RawDemoParser

from src.parsing.dto import ParsedMatch, ParsedPlayer, ParsedRound
from src.metrics.utility import calculate_utility_metrics
from src.metrics.entry import calculate_entry_metrics
from src.metrics.clutch import calculate_clutches
from src.metrics.trade import calculate_trade_metrics
from src.metrics.kast import calculate_kast_metrics
from src.metrics.multikill import calculate_multikill_metrics


class DemoParser:
    """
    Обёртка над demoparser2.

    Задача класса:
    1. прочитать сырую демку;
    2. нормализовать данные;
    3. собрать ParsedMatch;
    4. добавить Utility / Entry / Clutch.
    """

    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Файл демо не найден по пути: {file_path}"
            )

        self.file_path = file_path
        self.raw_parser = RawDemoParser(file_path)

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def parse(self) -> ParsedMatch:
        """
        Основной метод парсинга демо.
        """

        match_id = os.path.splitext(
            os.path.basename(self.file_path)
        )[0]

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------

        header = self.raw_parser.parse_header()

        map_name = (
            str(header.get("map_name", "unknown"))
            if header
            else "unknown"
        )

        # --------------------------------------------------------------
        # Rounds
        # --------------------------------------------------------------

        rounds = self._parse_rounds()
        rounds_played = len(rounds)

        # --------------------------------------------------------------
        # Players
        #
        # Базовые K / D / A / Damage / HS берём из финальных
        # scoreboard counters, а не считаем вручную по событиям.
        # --------------------------------------------------------------

        players = self._parse_players(
            rounds=rounds
        )

        # --------------------------------------------------------------
        # Final score
        #
        # round_end.winner показывает сторону CT/T,
        # выигравшую конкретный раунд.
        #
        # Это НЕ постоянная команда: команды меняются сторонами.
        #
        # Поэтому настоящий финальный счёт берём из
        # team_rounds_total на финальном игровом состоянии.
        # --------------------------------------------------------------

        (
            score_ct,
            score_t,
            winner_side,
            score_valid,
            score_error,
        ) = self._parse_final_score(
            rounds=rounds
        )

        # --------------------------------------------------------------
        # Duration
        # --------------------------------------------------------------

        duration_seconds = self._parse_duration_seconds(
            header=header,
            rounds=rounds
        )

        # --------------------------------------------------------------
        # Data Trust validation
        # --------------------------------------------------------------

        is_valid = (
            rounds_played > 0
            and score_valid
        )

        validation_error = None

        if rounds_played <= 0:
            validation_error = (
                "Unable to determine played rounds."
            )

        elif not score_valid:
            validation_error = score_error

        # --------------------------------------------------------------
        # Advanced metrics
        # --------------------------------------------------------------

        self._enrich_player_metrics(
            players=players,
            rounds_played=rounds_played
        )

        # --------------------------------------------------------------
        # Final DTO
        # --------------------------------------------------------------

        return ParsedMatch(
            match_id=match_id,
            map_name=map_name,
            duration_seconds=duration_seconds,
            rounds_played=rounds_played,
            score_ct=score_ct,
            score_t=score_t,
            winner_side=winner_side,
            players=players,
            rounds=rounds,
            is_valid=is_valid,
            validation_error=validation_error,
        )

    # ------------------------------------------------------------------
    # ROUNDS
    # ------------------------------------------------------------------

    def _parse_rounds(self) -> List[ParsedRound]:
        """
        Парсит реальные сыгранные раунды.

        Важно:
        - нет лимита в 24 раунда;
        - овертаймы учитываются;
        - пост-матчевые round_end отсекаются через
          cs_win_panel_match, если событие доступно.
        """

        round_events = self.raw_parser.parse_events(
            ["round_end"]
        )

        df_rounds = self._extract_dataframe(
            round_events
        )

        if df_rounds is None or df_rounds.empty:
            return []

        # --------------------------------------------------------------
        # Официальный конец матча
        # --------------------------------------------------------------

        match_end_tick = None

        try:
            win_panel_events = self.raw_parser.parse_events(
                ["cs_win_panel_match"]
            )

            df_win_panel = self._extract_dataframe(
                win_panel_events
            )

            if (
                df_win_panel is not None
                and not df_win_panel.empty
                and "tick" in df_win_panel.columns
            ):
                match_end_tick = df_win_panel["tick"].max()

        except Exception as exc:
            print(
                f"⚠️ Не удалось определить cs_win_panel_match: {exc}"
            )
            match_end_tick = None

        # --------------------------------------------------------------
        # Убираем события после официального окончания
        # --------------------------------------------------------------

        if (
            match_end_tick is not None
            and "tick" in df_rounds.columns
        ):
            df_valid_rounds = df_rounds[
                df_rounds["tick"] <= match_end_tick
            ].copy()
        else:
            df_valid_rounds = df_rounds.copy()

        parsed_rounds: List[ParsedRound] = []

        # --------------------------------------------------------------
        # Нормализация раундов
        # --------------------------------------------------------------

        for index, row in df_valid_rounds.iterrows():

            winner_side = self._normalize_side(
                row.get("winner")
            )

            round_num = self._safe_int(
                row.get("round"),
                default=index + 1
            )

            end_tick = self._safe_int(
                row.get("tick"),
                default=0
            )

            win_reason = str(
                row.get(
                    "reason",
                    "unknown"
                )
            )

            parsed_rounds.append(
                ParsedRound(
                    round_num=round_num,
                    winner_side=winner_side,
                    win_reason=win_reason,
                    end_tick=end_tick,
                )
            )

        return parsed_rounds

    # ------------------------------------------------------------------
    # PLAYERS
    # ------------------------------------------------------------------

    def _parse_players(
        self,
        rounds: List[ParsedRound]
    ) -> List[ParsedPlayer]:
        """
        Получает базовую статистику игроков из финальных
        игровых scoreboard counters.

        Используем:
        - kills_total
        - deaths_total
        - assists_total
        - damage_total
        - headshot_kills_total

        Почему не считаем Damage через player_hurt.dmg_health:
        dmg_health может содержать overkill damage.

        Например, если у игрока осталось 20 HP,
        смертельный выстрел может иметь dmg_health > 20.

        Scoreboard damage уже содержит правильную игровую
        итоговую статистику.
        """

        rounds_played = len(rounds)

        if rounds_played <= 0:
            return []

        # --------------------------------------------------------------
        # Последний подтверждённый сыгранный раунд
        # --------------------------------------------------------------

        final_tick = max(
            round_data.end_tick
            for round_data in rounds
        )

        if final_tick <= 0:
            return []

        # --------------------------------------------------------------
        # Финальные scoreboard counters
        # --------------------------------------------------------------

        try:
            player_ticks = self.raw_parser.parse_ticks(
                [
                    "kills_total",
                    "deaths_total",
                    "assists_total",
                    "damage_total",
                    "headshot_kills_total",
                ],
                ticks=[final_tick]
            )

        except Exception as exc:
            print(
                "⚠️ Не удалось получить "
                f"player scoreboard stats: {exc}"
            )
            return []

        if (
            player_ticks is None
            or not hasattr(player_ticks, "empty")
            or player_ticks.empty
        ):
            print(
                "⚠️ Player scoreboard stats пусты"
            )
            return []

        if "steamid" not in player_ticks.columns:
            print(
                "⚠️ В player scoreboard stats "
                "отсутствует steamid"
            )
            return []

        parsed_players: List[ParsedPlayer] = []

        # --------------------------------------------------------------
        # Один игрок = один SteamID
        # --------------------------------------------------------------

        for steam_id, group in player_ticks.groupby(
            "steamid"
        ):
            steam_id = str(steam_id)

            if steam_id in {
                "",
                "0",
                "None",
                "nan",
            }:
                continue

            # На выбранном final_tick обычно одна строка на игрока.
            # Но на всякий случай берём последнюю.
            if "tick" in group.columns:
                last_row = (
                    group
                    .sort_values("tick")
                    .iloc[-1]
                )
            else:
                last_row = group.iloc[-1]

            name = str(
                last_row.get(
                    "name",
                    "Unknown"
                )
            )

            kills = self._safe_int(
                last_row.get(
                    "kills_total",
                    0
                )
            )

            deaths = self._safe_int(
                last_row.get(
                    "deaths_total",
                    0
                )
            )

            assists = self._safe_int(
                last_row.get(
                    "assists_total",
                    0
                )
            )

            damage = self._safe_float(
                last_row.get(
                    "damage_total",
                    0.0
                )
            )

            headshots = self._safe_int(
                last_row.get(
                    "headshot_kills_total",
                    0
                )
            )

            parsed_players.append(
                ParsedPlayer(
                    steam_id=steam_id,
                    name=name,
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    damage=damage,
                    headshots=headshots,
                    rounds_played=rounds_played,
                )
            )

        return parsed_players

    # ------------------------------------------------------------------
    # ADVANCED METRICS
    # ------------------------------------------------------------------

    def _enrich_player_metrics(
        self,
        players: List[ParsedPlayer],
        rounds_played: int
    ) -> None:
        """
        Добавляет к игрокам:

        - Utility
        - Entry
        - Clutch

        Эти метрики пока проходят отдельный Data Trust аудит.
        """

        steam_ids = [
            player.steam_id
            for player in players
        ]

        # --------------------------------------------------------------
        # Utility
        # --------------------------------------------------------------

        try:
            utility_stats = calculate_utility_metrics(
                self.raw_parser
            )

        except Exception as exc:
            print(
                f"⚠️ Ошибка при расчёте Utility: {exc}"
            )
            utility_stats = {}

        # --------------------------------------------------------------
        # Entry
        # --------------------------------------------------------------

        try:
            entry_stats = calculate_entry_metrics(
                self.raw_parser
            )

        except Exception as exc:
            print(
                f"⚠️ Ошибка при расчёте Entry: {exc}"
            )
            entry_stats = {}

        # --------------------------------------------------------------
        # Clutch
        # --------------------------------------------------------------

        try:
            clutch_stats = calculate_clutches(
                self.raw_parser,
                steam_ids
            )

        except Exception as exc:
            print(
                f"⚠️ Ошибка при расчёте Clutch: {exc}"
            )
            clutch_stats = {}

        # --------------------------------------------------------------
        # Trade
        # --------------------------------------------------------------

        try:
            trade_kills, traded_deaths = calculate_trade_metrics(
                self.raw_parser,
                steam_ids,
            )

        except Exception as exc:
            print(
                f"Trade metrics calculation failed: {exc}"
            )
            trade_kills = {}
            traded_deaths = {}

        # KAST

        try:
            kast_stats = calculate_kast_metrics(
                self.raw_parser,
                steam_ids,
            )

        except Exception as exc:
            print(
                f"KAST metrics calculation failed: {exc}"
            )
            kast_stats = {}

        # Multikill

        try:
            multikill_stats = calculate_multikill_metrics(
                self.raw_parser,
                steam_ids,
            )

        except Exception as exc:
            print(
                f"Multikill metrics calculation failed: {exc}"
            )
            multikill_stats = {}

        # --------------------------------------------------------------
        # Записываем результаты в DTO
        # --------------------------------------------------------------

        for player in players:

            sid = player.steam_id

            # ----------------------------------------------------------
            # Utility
            # ----------------------------------------------------------

            utility_data = utility_stats.get(
                sid,
                {}
            )

            player.he_damage = self._safe_float(
                utility_data.get(
                    "he_damage",
                    0.0
                )
            )

            player.inferno_damage = self._safe_float(
                utility_data.get(
                    "inferno_damage",
                    0.0
                )
            )

            player.enemies_flashed = self._safe_int(
                utility_data.get(
                    "enemies_flashed",
                    0
                )
            )

            player.flash_duration = self._safe_float(
                utility_data.get(
                    "flash_duration",
                    0.0
                )
            )

            # ----------------------------------------------------------
            # Entry
            # ----------------------------------------------------------

            entry_data = entry_stats.get(
                sid,
                {}
            )

            player.entry_kills = self._safe_int(
                entry_data.get(
                    "entry_kills",
                    0
                )
            )

            player.entry_deaths = self._safe_int(
                entry_data.get(
                    "entry_deaths",
                    0
                )
            )

            # ----------------------------------------------------------
            # Clutch
            # ----------------------------------------------------------

            player.clutches_won = self._safe_int(
                clutch_stats.get(
                    sid,
                    0
                )
            )

            # ----------------------------------------------------------
            # Trade
            # ----------------------------------------------------------

            player.trade_kills = self._safe_int(
                trade_kills.get(
                    sid,
                    0
                )
            )

            player.traded_deaths = self._safe_int(
                traded_deaths.get(
                    sid,
                    0
                )
            )

            # KAST

            player.kast_rounds = self._safe_int(
                kast_stats.get(
                    sid,
                    0
                )
            )

            # Multikill

            multikill_data = multikill_stats.get(
                sid,
                {}
            )

            player.two_k_rounds = self._safe_int(
                multikill_data.get(
                    "two_k_rounds",
                    0
                )
            )

            player.three_k_rounds = self._safe_int(
                multikill_data.get(
                    "three_k_rounds",
                    0
                )
            )

            player.four_k_rounds = self._safe_int(
                multikill_data.get(
                    "four_k_rounds",
                    0
                )
            )

            player.five_k_rounds = self._safe_int(
                multikill_data.get(
                    "five_k_rounds",
                    0
                )
            )

    # ------------------------------------------------------------------
    # FINAL SCORE
    # ------------------------------------------------------------------

    def _parse_final_score(
        self,
        rounds: List[ParsedRound]
    ):
        """
        Получает настоящий финальный счёт матча.

        round_end.winner показывает сторону CT/T,
        выигравшую конкретный раунд.

        Команды меняются сторонами после halftime
        и могут менять стороны повторно в overtime.

        Поэтому настоящий командный счёт берём из
        team_rounds_total на последнем валидном round_end tick.

        В текущем DTO:
        score_ct / score_t означают счёт команды,
        находящейся соответственно за CT / T
        в финальном состоянии матча.
        """

        if not rounds:
            return (
                0,
                0,
                "UNKNOWN",
                False,
                "Unable to determine final score: no rounds."
            )

        # --------------------------------------------------------------
        # Последний подтверждённый сыгранный раунд
        # --------------------------------------------------------------

        final_tick = max(
            round_data.end_tick
            for round_data in rounds
        )

        if final_tick <= 0:
            return (
                0,
                0,
                "UNKNOWN",
                False,
                "Unable to determine final score tick."
            )

        # --------------------------------------------------------------
        # Получаем командное состояние
        # --------------------------------------------------------------

        try:
            df_score = self.raw_parser.parse_ticks(
                [
                    "team_num",
                    "team_name",
                    "team_rounds_total",
                ],
                ticks=[final_tick]
            )

        except Exception as exc:
            return (
                0,
                0,
                "UNKNOWN",
                False,
                f"Unable to parse final team score: {exc}"
            )

        if (
            df_score is None
            or not hasattr(df_score, "empty")
            or df_score.empty
        ):
            return (
                0,
                0,
                "UNKNOWN",
                False,
                "Final team state is empty."
            )

        required_columns = {
            "team_num",
            "team_rounds_total",
        }

        if not required_columns.issubset(
            set(df_score.columns)
        ):
            return (
                0,
                0,
                "UNKNOWN",
                False,
                "Final team score columns are missing."
            )

        scores = {}

        # team_num:
        # 3 = CT
        # 2 = TERRORIST

        for team_num, side in (
            (3, "CT"),
            (2, "T"),
        ):

            team_rows = df_score[
                df_score["team_num"].apply(
                    lambda value: self._safe_int(
                        value,
                        default=-1
                    ) == team_num
                )
            ]

            if team_rows.empty:
                return (
                    0,
                    0,
                    "UNKNOWN",
                    False,
                    f"Final state for {side} team is missing."
                )

            # ----------------------------------------------------------
            # У всех игроков одной команды на одном tick
            # должен быть одинаковый team_rounds_total.
            # ----------------------------------------------------------

            team_scores = {
                self._safe_int(
                    value,
                    default=-1
                )
                for value
                in team_rows["team_rounds_total"]
            }

            team_scores = {
                value
                for value in team_scores
                if value >= 0
            }

            if len(team_scores) != 1:
                return (
                    0,
                    0,
                    "UNKNOWN",
                    False,
                    f"Inconsistent final score for {side}."
                )

            scores[side] = team_scores.pop()

        score_ct = scores["CT"]
        score_t = scores["T"]

        # --------------------------------------------------------------
        # DATA TRUST INVARIANT
        #
        # Каждый сыгранный раунд должен добавить ровно одно очко
        # одной из двух команд.
        # --------------------------------------------------------------

        if (
            score_ct + score_t
            != len(rounds)
        ):
            return (
                score_ct,
                score_t,
                "UNKNOWN",
                False,
                (
                    "Final score does not match round count: "
                    f"{score_ct} + {score_t} != {len(rounds)}."
                )
            )

        # --------------------------------------------------------------
        # Winner
        #
        # winner_side означает сторону, на которой победившая
        # команда находилась в финальном состоянии.
        # --------------------------------------------------------------

        if score_ct > score_t:
            winner_side = "CT"

        elif score_t > score_ct:
            winner_side = "T"

        else:
            winner_side = "UNKNOWN"

        return (
            score_ct,
            score_t,
            winner_side,
            True,
            None,
        )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_dataframe(events):
        """
        demoparser2 может возвращать DataFrame напрямую
        или структуру со списком/tuple.

        Приводим это к одному формату.
        """

        if events is None:
            return None

        # DataFrame
        if hasattr(events, "iterrows"):
            return events

        # list
        if isinstance(events, list) and len(events) > 0:

            first = events[0]

            # tuple: (event_name, dataframe)
            if (
                isinstance(first, tuple)
                and len(first) >= 2
            ):
                return first[1]

            # просто dataframe в списке
            return first

        return None

    @staticmethod
    def _normalize_side(value) -> str:
        """
        Приводит разные варианты winner
        к CT / T / UNKNOWN.
        """

        if value is None:
            return "UNKNOWN"

        value_str = str(value).strip().upper()

        # CT
        if value_str in {
            "CT",
            "3",
            "COUNTER-TERRORIST",
            "COUNTER_TERRORIST",
        }:
            return "CT"

        # T
        if value_str in {
            "T",
            "2",
            "TERRORIST",
            "TERRORISTS",
        }:
            return "T"

        return "UNKNOWN"

    @staticmethod
    def _safe_int(
        value,
        default: int = 0
    ) -> int:
        """
        Безопасное преобразование значения в int.
        """

        try:
            if value is None:
                return default

            return int(value)

        except (
            TypeError,
            ValueError
        ):
            return default

    @staticmethod
    def _safe_float(
        value,
        default: float = 0.0
    ) -> float:
        """
        Безопасное преобразование значения в float.
        """

        try:
            if value is None:
                return default

            return float(value)

        except (
            TypeError,
            ValueError
        ):
            return default

    def _parse_duration_seconds(
        self,
        header,
        rounds: List[ParsedRound]
    ) -> int:
        """
        Пытается получить длительность из header.

        Мы специально не вычисляем её приблизительно через tick,
        потому что неверная длительность хуже, чем 0.

        Если библиотека/конкретная демка предоставляет
        playback_time / duration, используем их.
        """

        if header:

            possible_fields = [
                "duration_seconds",
                "duration",
                "playback_time",
                "duration_sec",
            ]

            for field_name in possible_fields:

                if field_name not in header:
                    continue

                value = header.get(
                    field_name
                )

                duration = self._safe_int(
                    value,
                    default=0
                )

                if duration > 0:
                    return duration

        return 0
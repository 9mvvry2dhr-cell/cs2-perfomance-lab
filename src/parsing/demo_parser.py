from pathlib import Path
import pandas as pd
from demoparser2 import DemoParser as RawDemoParser
from src.domain.dto import ParsedMatch, ParsedPlayer


class DemoParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.raw_parser = RawDemoParser(str(self.file_path))

    def parse(self) -> ParsedMatch:
        header = self.raw_parser.parse_header()
        map_name = header.get("map_name", "unknown")

        # 1. Получаем общее количество раундов через тики правил
        rounds_played = 0
        try:
            game_rules = self.raw_parser.parse_ticks(["total_rounds_played"])
            if isinstance(game_rules, pd.DataFrame) and not game_rules.empty:
                rounds_played = int(game_rules["total_rounds_played"].max())
        except Exception as e:
            print(f"⚠️ Ошибка при чтении total_rounds_played: {e}")

        # 2. Извлекаем события завершения раундов для расчета счета CT:T
        score_ct = 0
        score_t = 0

        try:
            round_events = self.raw_parser.parse_events(["round_end"])

            # Извлекаем DataFrame из ответа demoparser2
            df_events = None
            if isinstance(round_events, pd.DataFrame):
                df_events = round_events
            elif isinstance(round_events, list) and len(round_events) > 0:
                for item in round_events:
                    if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], pd.DataFrame):
                        df_events = item[1]
                        break
                    elif isinstance(item, pd.DataFrame):
                        df_events = item
                        break

            if df_events is not None and not df_events.empty:
                if rounds_played == 0:
                    rounds_played = len(df_events)

                if "winner" in df_events.columns:
                    # Подсчитываем победителей по строковым значениям 'CT' и 'T' / 3 и 2
                    score_ct = int((df_events["winner"].astype(str).str.upper() == "CT").sum())
                    score_t = int((df_events["winner"].astype(str).str.upper() == "T").sum())

                    # Резервный подсчет, если используются числовые кодировки
                    if score_ct == 0 and score_t == 0:
                        score_t = int((df_events["winner"] == 2).sum())
                        score_ct = int((df_events["winner"] == 3).sum())

        except Exception as e:
            print(f"⚠️ Ошибка при парсинге round_end: {e}")

        # Определяем победителя
        if score_ct > score_t:
            winner_side = "CT"
        elif score_t > score_ct:
            winner_side = "T"
        else:
            winner_side = "Draw"

        # 3. Считываем итоговую статистику игроков
        player_ticks = self.raw_parser.parse_ticks([
            "kills_total",
            "deaths_total",
            "assists_total",
            "damage_total",
            "headshot_kills_total"
        ])

        parsed_players = []
        if isinstance(player_ticks, pd.DataFrame) and not player_ticks.empty:
            last_tick = player_ticks["tick"].max()
            final_stats = player_ticks[player_ticks["tick"] == last_tick]

            for _, row in final_stats.iterrows():
                steam_id = str(row.get("steamid", row.get("name", "0")))
                player = ParsedPlayer(
                    steam_id=steam_id,
                    name=str(row.get("name", "Unknown")),
                    kills=int(row.get("kills_total", 0)),
                    deaths=int(row.get("deaths_total", 0)),
                    assists=int(row.get("assists_total", 0)),
                    damage=float(row.get("damage_total", 0.0)),
                    headshots=int(row.get("headshot_kills_total", 0)),
                    rounds_played=rounds_played if rounds_played > 0 else 1
                )
                parsed_players.append(player)

        match_id = self.file_path.stem

        return ParsedMatch(
            match_id=match_id,
            map_name=map_name,
            duration_seconds=0,
            rounds_played=rounds_played,
            score_ct=score_ct,
            score_t=score_t,
            winner_side=winner_side,
            players=parsed_players
        )
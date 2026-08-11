from pathlib import Path
import pandas as pd
from src.parsing.dto import ParsedMatch, ParsedPlayer, ParsedRound
from demoparser2 import DemoParser as RawDemoParser


class DemoParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.raw_parser = RawDemoParser(str(self.file_path))

    def parse(self) -> ParsedMatch:
        header = self.raw_parser.parse_header()
        map_name = header.get("map_name", "unknown")

        rounds_played = 0
        is_valid = True
        validation_error = None

        try:
            game_rules = self.raw_parser.parse_ticks(["total_rounds_played"])
            if isinstance(game_rules, pd.DataFrame) and not game_rules.empty:
                rounds_played = int(game_rules["total_rounds_played"].max())
        except Exception as e:
            print(f"⚠️ Ошибка при чтении total_rounds_played: {e}")

        score_ct = 0
        score_t = 0
        parsed_rounds = []

        try:
            round_events = self.raw_parser.parse_events(["round_end"])

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
                    score_ct = int((df_events["winner"].astype(str).str.upper() == "CT").sum())
                    score_t = int((df_events["winner"].astype(str).str.upper() == "T").sum())

                    if score_ct == 0 and score_t == 0:
                        score_t = int((df_events["winner"] == 2).sum())
                        score_ct = int((df_events["winner"] == 3).sum())

                for idx, row in df_events.iterrows():
                    w_side = str(row.get("winner", "UNKNOWN"))
                    if w_side == "3":
                        w_side = "CT"
                    elif w_side == "2":
                        w_side = "T"
                        
                    parsed_rounds.append(
                        ParsedRound(
                            round_num=int(row.get("round", idx + 1)),
                            winner_side=w_side.upper(),
                            win_reason=str(row.get("reason", "unknown")),
                            end_tick=int(row.get("tick", 0))
                        )
                    )

        except Exception as e:
            print(f"⚠️ Ошибка при парсинге round_end: {e}")

        # Проверка Data Trust: Раунды не определены
        if rounds_played <= 0:
            is_valid = False
            validation_error = "Unable to determine rounds_played. Derived metrics skipped."

        if score_ct > score_t:
            winner_side = "CT"
        elif score_t > score_ct:
            winner_side = "T"
        else:
            winner_side = "Draw"

        player_ticks = self.raw_parser.parse_ticks([
            "kills_total",
            "deaths_total",
            "assists_total",
            "damage_total",
            "headshot_kills_total"
        ])

        parsed_players = []
        if isinstance(player_ticks, pd.DataFrame) and not player_ticks.empty:
            # P0 Fix: Финальное состояние определяется индивидуально по каждому игроку (группировка)
            id_col = "steamid" if "steamid" in player_ticks.columns else "name"
            
            for player_id, group in player_ticks.groupby(id_col):
                if str(player_id) in ["0", "None", ""]:
                    continue

                last_row = group.sort_values("tick").iloc[-1]

                raw_steam_id = str(last_row.get("steamid", ""))
                if not raw_steam_id or raw_steam_id == "0":
                    raw_steam_id = f"UNKNOWN_{last_row.get('name', 'player')}"

                player = ParsedPlayer(
                    steam_id=raw_steam_id,
                    name=str(last_row.get("name", "Unknown")),
                    kills=int(last_row.get("kills_total", 0)),
                    deaths=int(last_row.get("deaths_total", 0)),
                    assists=int(last_row.get("assists_total", 0)),
                    damage=float(last_row.get("damage_total", 0.0)),
                    headshots=int(last_row.get("headshot_kills_total", 0)),
                    rounds_played=rounds_played
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
            players=parsed_players,
            rounds=parsed_rounds,
            is_valid=is_valid,
            validation_error=validation_error
        )
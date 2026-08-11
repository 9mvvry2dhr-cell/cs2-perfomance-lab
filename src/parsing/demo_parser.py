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

        team_a_score = 0  # Команда, стартовавшая за CT (1-12 раунды)
        team_b_score = 0  # Команда, стартовавшая за T (1-12 раунды)
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
                df_valid_rounds = df_events[df_events["winner"].isin([2, 3, "2", "3", "CT", "T"])].copy()
                
                if len(df_valid_rounds) > 24:
                    df_valid_rounds = df_valid_rounds.iloc[-24:]

                rounds_played = len(df_valid_rounds)

                for idx, (_, row) in enumerate(df_valid_rounds.iterrows()):
                    actual_round_num = idx + 1
                    w_side = str(row.get("winner", "")).upper()

                    is_ct_win = w_side in ["3", "CT"]
                    is_t_win = w_side in ["2", "T"]

                    if actual_round_num <= 12:
                        if is_ct_win:
                            team_a_score += 1
                        elif is_t_win:
                            team_b_score += 1
                    else:
                        if is_ct_win:
                            team_b_score += 1
                        elif is_t_win:
                            team_a_score += 1

                    parsed_rounds.append(
                        ParsedRound(
                            round_num=actual_round_num,
                            winner_side="CT" if is_ct_win else ("T" if is_t_win else "UNKNOWN"),
                            win_reason=str(row.get("reason", "unknown")),
                            end_tick=int(row.get("tick", 0))
                        )
                    )

        except Exception as e:
            print(f"⚠️ Ошибка при парсинге round_end: {e}")

        if rounds_played <= 0:
            is_valid = False
            validation_error = "Unable to determine rounds_played. Derived metrics skipped."

        if team_a_score >= team_b_score:
            score_ct = team_a_score
            score_t = team_b_score
            winner_side = "Team A"
        else:
            score_ct = team_b_score
            score_t = team_a_score
            winner_side = "Team B"

        player_ticks = self.raw_parser.parse_ticks([
            "kills_total",
            "deaths_total",
            "assists_total",
            "damage_total",
            "headshot_kills_total"
        ])

        parsed_players = []
        if isinstance(player_ticks, pd.DataFrame) and not player_ticks.empty:
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
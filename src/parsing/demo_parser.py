from pathlib import Path
from demoparser2 import DemoParser as RawDemoParser
from src.domain.dto import ParsedMatch, ParsedPlayer


class DemoParser:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.raw_parser = RawDemoParser(str(self.file_path))

    def parse(self) -> ParsedMatch:
        header = self.raw_parser.parse_header()
        map_name = header.get("map_name", "unknown")

        # 1. Считаем раунды
        game_rules = self.raw_parser.parse_ticks(["total_rounds_played"])
        max_rounds = 0
        if not game_rules.empty:
            max_rounds = int(game_rules["total_rounds_played"].max())

        # 2. Собираем финальные тики игроков
        player_ticks = self.raw_parser.parse_ticks([
            "kills_total",
            "deaths_total",
            "assists_total",
            "damage_total",
            "headshot_kills_total"
        ])

        parsed_players = []
        if not player_ticks.empty:
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
                    rounds_played=max_rounds
                )
                parsed_players.append(player)

        match_id = self.file_path.stem

        return ParsedMatch(
            match_id=match_id,
            map_name=map_name,
            duration_seconds=0,
            rounds_played=max_rounds,
            score_ct=0,
            score_t=0,
            winner_side="Unknown",
            players=parsed_players
        )
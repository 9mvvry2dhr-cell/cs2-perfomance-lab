from pathlib import Path
from datetime import datetime
import uuid
from demoparser2 import DemoParser as ValveDemoParser
from src.domain.models import Match, PlayerStats


class DemoParser:
    """Отвечает за парсинг CS2 .dem файлов с помощью parse_player_info()."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def parse(self) -> Match:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.file_path}")

        parser = ValveDemoParser(str(self.file_path))

        # 1. Извлекаем название карты
        try:
            header = parser.parse_header()
            map_name = header.get("map_name", "de_ancient") if header else "de_ancient"
        except Exception:
            map_name = "de_ancient"

        # 2. Считаем количество раундов через событие round_start
        total_rounds = 24
        try:
            round_starts = parser.parse_event("round_start")
            if round_starts is not None and not round_starts.empty:
                total_rounds = max(1, len(round_starts))
        except Exception:
            pass

        # 3. Достаем итоговую статистику игроков через parse_player_info()
        players = []
        try:
            df_players = parser.parse_player_info()
            if df_players is not None and not df_players.empty:
                # Берем последние уникальные записи по каждому steamid
                df_last = df_players.drop_duplicates(subset=["steamid"], keep="last")

                for _, row in df_last.iterrows():
                    steam_id = str(row.get("steamid", "0"))
                    if steam_id in ["0", "None", ""]:
                        continue

                    kills = int(row.get("kills", 0))
                    deaths = int(row.get("deaths", 0))
                    assists = int(row.get("assists", 0))
                    damage = int(row.get("damage", 0))
                    name = str(row.get("name", "Player"))

                    players.append(
                        PlayerStats(
                            steam_id=steam_id,
                            name=name,
                            kills=kills,
                            deaths=deaths,
                            assists=assists,
                            damage=damage,
                            headshots=0,  # Хедшоты дотянем из событий при необходимости
                            rounds_played=total_rounds,
                        )
                    )
        except Exception:
            pass

        # Если данные не распарсились, создаем дефолтную запись
        if not players:
            players.append(
                PlayerStats(
                    steam_id="0",
                    name="Unknown Player",
                    kills=0,
                    deaths=0,
                    rounds_played=total_rounds,
                )
            )

        # 4. Достаем счет из round_end
        score_ct, score_t = 0, 0
        try:
            round_ends = parser.parse_event("round_end")
            if round_ends is not None and not round_ends.empty:
                for _, row in round_ends.iterrows():
                    winner = row.get("winner")
                    if winner == 2:
                        score_t += 1
                    elif winner == 3:
                        score_ct += 1
        except Exception:
            pass

        winner_side = "CT" if score_ct > score_t else ("T" if score_t > score_ct else "Draw")

        return Match(
            match_id=f"match_{uuid.uuid4().hex[:8]}",
            map_name=map_name,
            played_at=datetime.now(),
            duration_seconds=total_rounds * 115,
            score_ct=score_ct,
            score_t=score_t,
            winner_side=winner_side,
            players=players
        )
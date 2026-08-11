from pathlib import Path
from datetime import datetime
import uuid
from demoparser2 import DemoParser as ValveDemoParser
from src.domain.models import Match, PlayerStats


# Список ключевых накопительных свойств из сетевых тиков движка
PLAYER_GAME_PROPS = [
    "is_warmup_period",
    "total_rounds_played",
    "team_rounds_total",
    "team_name",
    "kills_total",
    "deaths_total",
    "assists_total",
    "headshot_kills_total",
    "damage_total",
]


class DemoParser:
    """Отвечает за парсинг CS2 .dem файлов через накопительные Game-State тики."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def parse(self) -> Match:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.file_path}")

        parser = ValveDemoParser(str(self.file_path))

        # 1. Извлекаем карту
        try:
            header = parser.parse_header()
            map_name = header.get("map_name", "de_ancient") if header else "de_ancient"
        except Exception:
            map_name = "de_ancient"

        # 2. Получаем тики игроков и состояние матча
        total_rounds = 1
        players = []
        score_ct, score_t = 0, 0

        try:
            df_ticks = parser.parse_ticks(PLAYER_GAME_PROPS)
            
            if df_ticks is not None and not df_ticks.empty:
                # Фильтруем разминку и берем финальный тик матча
                last_tick = df_ticks["tick"].max()
                final_df = df_ticks[(df_ticks["tick"] == last_tick) & (df_ticks["is_warmup_period"] == False)].copy()

                if not final_df.empty:
                    # Извлекаем общее количество сыгранных раундов из первого валидного игрока
                    total_rounds = int(final_df["total_rounds_played"].iloc[0])
                    total_rounds = max(1, total_rounds)

                    # Извлекаем счет сторон из сетевых структур команд
                    for _, row in final_df.iterrows():
                        team_name = str(row.get("team_name", ""))
                        rounds_total = int(row.get("team_rounds_total", 0))
                        if "CT" in team_name:
                            score_ct = rounds_total
                        elif "TERRORIST" in team_name:
                            score_t = rounds_total

                    # Собираем статистику каждого игрока
                    for _, row in final_df.iterrows():
                        steam_id = str(row.get("steamid", "0"))
                        if steam_id in ["0", "None", ""]:
                            continue

                        name = str(row.get("name", "Player"))
                        kills = int(row.get("kills_total", 0))
                        deaths = int(row.get("deaths_total", 0))
                        assists = int(row.get("assists_total", 0))
                        headshots = int(row.get("headshot_kills_total", 0))
                        damage = int(row.get("damage_total", 0))

                        players.append(
                            PlayerStats(
                                steam_id=steam_id,
                                name=name,
                                kills=kills,
                                deaths=deaths,
                                assists=assists,
                                damage=damage,
                                headshots=headshots,
                                rounds_played=total_rounds,
                            )
                        )
        except Exception:
            pass

        # Если данные по тикам не сработали, создаем заглушку
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
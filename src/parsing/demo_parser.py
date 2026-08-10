from pathlib import Path
from datetime import datetime
import uuid
from src.domain.models import Match, PlayerStats


class DemoParser:
    """Отвечает за извлечение игровых данных из CS2 .dem файлов."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def parse(self) -> Match:
        """
        Разбирает .dem файл и возвращает объект Match.
        Сейчас содержит тестовую генерацию структуры для отладки Pipeline.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.file_path}")

        # Генерируем тестовый матч для проверки связки всего приложения
        match_id = f"match_{uuid.uuid4().hex[:8]}"
        
        player = PlayerStats(
            steam_id="76561198000000000",
            name="Player",
            kills=18,
            deaths=12,
            assists=5,
            damage=2100,
            headshots=10,
            rounds_played=22,
            first_kills=3,
            first_deaths=2,
            flash_assists=4,
            utility_damage=150
        )

        match = Match(
            match_id=match_id,
            map_name="de_mirage",
            played_at=datetime.now(),
            duration_seconds=2400,
            score_ct=13,
            score_t=9,
            winner_side="CT",
            players=[player]
        )

        return match
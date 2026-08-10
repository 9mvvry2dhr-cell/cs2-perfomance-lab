from pathlib import Path
from src.parsing.demo_parser import DemoParser
from src.database.matches import save_match
from src.domain.models import Match


class DemoService:
    """Организует полный цикл обработки демо-файла."""

    @staticmethod
    def process_demo_file(file_path: Path) -> Match:
        # 1. Парсим файл
        parser = DemoParser(file_path)
        match_data = parser.parse()

        # 2. Сохраняем в БД
        save_match(match_data)

        # 3. Возвращаем результат
        return match_data
from pathlib import Path
from src.parsing.demo_parser import DemoParser
from src.database.matches import save_match


class DemoService:
    @staticmethod
    def process_demo_file(file_path: Path):
        parser = DemoParser(file_path)
        match_obj = parser.parse()
        return save_match(match_obj)
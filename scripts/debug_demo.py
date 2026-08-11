import sys
from pathlib import Path
from src.parsing.demo_parser import DemoParser


def test_parser(demo_path: str):
    path = Path(demo_path)
    if not path.exists():
        print(f"❌ Файл не найден: {path}")
        return

    print(f"🔍 Тестирование DTO и Round Events: {path.name}\n" + "=" * 50)
    
    parser = DemoParser(str(path))
    parsed_match = parser.parse()

    print(f"🗺️  Карта: {parsed_match.map_name}")
    print(f"🏆 Победитель: {parsed_match.winner_side}")
    print(f"🔢 Счёт: CT {parsed_match.score_ct} : {parsed_match.score_t} T")
    print(f"🎯 Всего раундов: {parsed_match.rounds_played}\n")

    print("📊 Игроки (из DTO):")
    for p in parsed_match.players:
        print(
            f"  • {p.name:<20} | K: {p.kills:<2} | D: {p.deaths:<2} | "
            f"DMG: {p.damage:<6.0f} | ADR: {p.adr:<5.1f} | HS%: {p.hs_percent}%"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/debug_demo.py <путь_к_файлу.dem>")
    else:
        test_parser(sys.argv[1])
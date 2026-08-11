import sys
import time
from pathlib import Path

# Гарантируем добавление корня проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.parsing.demo_parser import DemoParser


def main():
    print("🚀 Скрипт запущен!")
    print("🔎 Ищем демо-файлы...")

    found_demos = list(PROJECT_ROOT.rglob("*.dem"))

    if not found_demos:
        print("❌ Ошибка: В проекте не найдено ни одного файла .dem!")
        return

    target_demo = found_demos[0]
    print(f"📁 Найдена демка: {target_demo.name}")
    print("⏳ Парсим...")

    start_time = time.time()
    parser = DemoParser(str(target_demo))
    parsed_match = parser.parse()
    elapsed = time.time() - start_time

    print(f"✅ Готово за {elapsed:.2f} сек.!\n")
    print("=" * 60)
    print(f"🎮 МАТЧ: {parsed_match.match_id}")
    print(f"🗺  Карта: {parsed_match.map_name}")
    print(f"📊 Валидность: {'✅ VALID' if parsed_match.is_valid else '❌ INVALID'}")
    print(f"🏆 Счет: {parsed_match.score_ct} : {parsed_match.score_t}")
    print(f"🔢 Всего раундов: {parsed_match.rounds_played}")
    print("=" * 60)

    print("\n👥 СТАТИСТИКА ИГРОКОВ:\n")
    header = f"{'SteamID':<20} | {'Nickname':<15} | {'K':<3} | {'D':<3} | {'A':<3} | {'HS':<3} | {'Damage':<7} | {'ADR':<6} | {'K/D':<5}"
    print(header)
    print("-" * len(header))

    for p in parsed_match.players:
        adr_str = f"{p.damage / parsed_match.rounds_played:.1f}" if parsed_match.rounds_played > 0 else "N/A"
        kd_str = f"{p.kills / max(1, p.deaths):.2f}"

        print(
            f"{p.steam_id:<20} | "
            f"{p.name[:15]:<15} | "
            f"{p.kills:<3} | "
            f"{p.deaths:<3} | "
            f"{p.assists:<3} | "
            f"{p.headshots:<3} | "
            f"{p.damage:<7.0f} | "
            f"{adr_str:<6} | "
            f"{kd_str:<5}"
        )

    print("=" * 60)

# Прямой вызов функции
main()
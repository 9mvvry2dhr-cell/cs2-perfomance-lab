import sys
import time
from pathlib import Path

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.parsing.demo_parser import DemoParser


def main():
    print("🚀 Скрипт проверки запущен!")
    print("🔎 Ищем демо-файлы в проекте...")

    found_demos = list(PROJECT_ROOT.rglob("*.dem"))

    if not found_demos:
        print("❌ Ошибка: В проекте не найдено ни одного файла .dem!")
        return

    target_demo = found_demos[0]
    print(f"📁 Найдена демка: {target_demo.name}")
    print("⏳ Парсим полную статистику (K/D, ADR, Utility, Entry, Clutches)...")

    start_time = time.time()
    parser = DemoParser(str(target_demo))
    parsed_match = parser.parse()
    elapsed = time.time() - start_time

    print(f"✅ Успешно распаршено за {elapsed:.2f} сек.!\n")
    print("=" * 105)
    print(f"🎮 МАТЧ: {parsed_match.match_id}")
    print(f"🗺  Карта: {parsed_match.map_name}")
    status = "✅ VALID" if parsed_match.is_valid else "❌ INVALID"
    print(f"📊 Статус: {status}")
    print(f"🏆 Счет: {parsed_match.score_ct} : {parsed_match.score_t}")
    print(f"🔢 Всего раундов: {parsed_match.rounds_played}")
    print("=" * 105)

    print("\n👥 ПОЛНАЯ СТАТИСТИКА ИГРОКОВ:\n")

    header = f"{'Nickname':<15} | {'K/D':<5} | {'ADR':<5} | {'HE Dmg':<7} | {'Molotov':<7} | {'Flashed':<7} | {'Flash Sec':<9} | {'Entry (K/D)':<11} | {'Clutches':<8}"
    print(header)
    print("-" * len(header))

    for p in parsed_match.players:
        if parsed_match.rounds_played > 0:
            adr_str = f"{p.damage / parsed_match.rounds_played:.1f}"
        else:
            adr_str = "N/A"

        kd_str = f"{p.kills / max(1, p.deaths):.2f}"
        entry_str = f"{p.entry_kills}/{p.entry_deaths}"

        line = (
            f"{p.name[:15]:<15} | "
            f"{kd_str:<5} | "
            f"{adr_str:<5} | "
            f"{p.he_damage:<7.0f} | "
            f"{p.inferno_damage:<7.0f} | "
            f"{p.enemies_flashed:<7} | "
            f"{p.flash_duration:<9.1f} | "
            f"{entry_str:<11} | "
            f"{p.clutches_won:<8}"
        )
        print(line)

    print("=" * 105)


if __name__ == "__main__":
    main()
from pathlib import Path
import sys
import time

# Добавляем корень проекта в sys.path
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
  print("⏳ Парсим метрики (включая Utility и Entry Kills)...")

  start_time = time.time()
  parser = DemoParser(str(target_demo))
  parsed_match = parser.parse()
  elapsed = time.time() - start_time

  print(f"✅ Готово за {elapsed:.2f} сек.!\n")
  print("=" * 85)
  print(f"🎮 МАТЧ: {parsed_match.match_id}")
  print(f"🗺  Карта: {parsed_match.map_name}")
  print(
      "📊 Валидность:"
      f" {'✅ VALID' if parsed_match.is_valid else '❌ INVALID'}"
  )
  print(f"🏆 Счет: {parsed_match.score_ct} : {parsed_match.score_t}")
  print(f"🔢 Всего раундов: {parsed_match.rounds_played}")
  print("=" * 85)

  print("\n👥 РАСШИРЕННАЯ СТАТИСТИКА ИГРОКОВ:\n")
  header = (
      f"{'Nickname':<15} | {'K/D':<5} | {'ADR':<5} | {'HE Dmg':<7} | {'Molotov':<7}"
      f" | {'Flashed':<7} | {'Flash Sec':<9} | {'Entry (K/D)':<11}"
  )
  print(header)
  print("-" * len(header))

  for p in parsed_match.players:
    adr_str = (
        f"{p.damage / parsed_match.rounds_played:.1f}"
        if parsed_match.rounds_played > 0
        else "N/A"
    )
    kd_str = f"{p.kills / max(1, p.deaths):.2f}"
    entry_str = f"{p.entry_kills}/{p.entry_deaths}"

    print(
        f"{p.name[:15]:<15} | "
        f"{kd_str:<5} | "
        f"{adr_str:<5} | "
        f"{p.he_damage:<7.0f} | "
        f"{p.inferno_damage:<7.0f} | "
        f"{p.enemies_flashed:<7} | "
        f"{p.flash_duration:<9.1f} | "
        f"{entry_str:<11}"
    )

  print("=" * 85)


main()
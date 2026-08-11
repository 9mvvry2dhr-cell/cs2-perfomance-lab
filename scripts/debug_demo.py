import sys
from pathlib import Path
from demoparser2 import DemoParser


def analyze_demo(demo_path: str):
    path = Path(demo_path)
    if not path.exists():
        print(f"❌ Файл не найден: {path}")
        return

    print(f"🔍 Анализ демки: {path.name}\n" + "=" * 50)
    parser = DemoParser(str(path))

    # 1. Заголовки / Базовая информация
    header = parser.parse_header()
    print("📋 HEADER INFO:")
    for k, v in header.items():
        print(f"  • {k}: {v}")

    # 2. Проверка зафиксированных раундов и фаз игры
    print("\n🎮 GAME PHASES & ROUNDS:")
    try:
        game_rules = parser.parse_ticks(
            ["is_warmup_period", "is_match_started", "total_rounds_played"]
        )
        print(f"  • Всего тиков с правилами: {len(game_rules)}")
        if not game_rules.empty:
            max_rounds = game_rules["total_rounds_played"].max()
            print(f"  • Макс. total_rounds_played: {max_rounds}")
    except Exception as e:
        print(f"  ⚠️ Ошибка при чтении game_rules: {e}")

    # 3. Финальная статистика игроков из тиков
    print("\n📊 PLAYER STATS (Raw end-game props):")
    try:
        player_stats = parser.parse_ticks(
            [
                "kills_total",
                "deaths_total",
                "assists_total",
                "damage_total",
                "headshot_kills_total",
            ]
        )

        if not player_stats.empty:
            last_tick = player_stats["tick"].max()
            final_stats = player_stats[player_stats["tick"] == last_tick]

            for _, row in final_stats.iterrows():
                name = row.get("name", row.get("steamid", "Unknown"))
                kills = row.get("kills_total", 0)
                deaths = row.get("deaths_total", 0)
                damage = row.get("damage_total", 0)
                print(
                    f"  • {name:<20} | K: {kills:<2} | D: {deaths:<2} | DMG: {damage}"
                )
    except Exception as e:
        print(f"  ⚠️ Ошибка при чтении player_stats: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/debug_demo.py <путь_к_файлу.dem>")
    else:
        analyze_demo(sys.argv[1])
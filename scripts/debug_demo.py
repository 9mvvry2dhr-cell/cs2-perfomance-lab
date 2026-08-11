import sys
from pathlib import Path
from demoparser2 import DemoParser

DEMO_PATH = r"D:\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays\match730_003829751258281935387_0710047347_187.dem"

def main():
    demo_file = Path(DEMO_PATH)
    if not demo_file.exists():
        print(f"❌ Файл не найден: {demo_file}")
        sys.exit(1)

    parser = DemoParser(str(demo_file))

    # Запрашиваем поля итоговой статистики игроков
    player_props = [
        "is_warmup_period",
        "total_rounds_played",
        "kills_total",
        "deaths_total",
        "assists_total",
        "headshot_kills_total",
        "damage_total",
    ]

    print("\n--- Финальная статистика игроков (последний тик матча) ---")
    df = parser.parse_ticks(player_props)
    
    if df is not None and not df.empty:
        # Берем только последний тик (финал матча) и фильтруем разминку
        last_tick = df["tick"].max()
        final_df = df[(df["tick"] == last_tick) & (df["is_warmup_period"] == False)]

        print(final_df[["name", "steamid", "kills_total", "deaths_total", "damage_total", "total_rounds_played"]].to_string())

        # Ищем статистику твоей учетки (kbn_san)
        my_stats = final_df[final_df["name"].str.contains("kbn_san", case=False, na=False)]
        if not my_stats.empty:
            row = my_stats.iloc[0]
            rounds = row["total_rounds_played"]
            damage = row["damage_total"]
            adr = round(damage / max(1, rounds), 1)
            print("\n" + "="*40)
            print(f"🎯 ТОЧНЫЙ ADR ИГРОКА kbn_san:")
            print(f" • Урон: {damage}")
            print(f" • Раундов: {rounds}")
            print(f" • Рассчитанный ADR: {adr}")
            print("="*40)

if __name__ == "__main__":
    main()
import sys
from pathlib import Path
from demoparser2 import DemoParser as RawDemoParser

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    demo_files = list(PROJECT_ROOT.glob("*.dem"))
    if not demo_files:
        print("❌ .dem файлы не найдены!")
        return

    demo_path = demo_files[0]
    print(f"🔎 Диагностика файла: {demo_path.name}\n")
    parser = RawDemoParser(str(demo_path))

    # 1. Диагностика round_end
    round_end_events = parser.parse_events(["round_end"])
    print("--- 1. РАУНДЫ (round_end) ---")
    if round_end_events:
        df_round_end = round_end_events[0][1] if isinstance(round_end_events, list) else round_end_events
        print(f"Доступные колонки: {list(df_round_end.columns)}")
        print(f"Всего событий round_end: {len(df_round_end)}")
        print(df_round_end[["tick", "winner", "reason"]].to_string())
    else:
        print("События round_end не найдены!")

    # 2. Проверка дополнительных событий фреймворка
    print("\n--- 2. ПРОВЕРКА СОБЫТИЙ СТАРТА / РЕСТАРТА ---")
    try:
        start_events = parser.parse_events(["round_start", "round_freeze_end", "cs_win_panel_match"])
        for evt in start_events:
            evt_name = evt[0] if isinstance(evt, tuple) else "event"
            df_evt = evt[1] if isinstance(evt, tuple) else evt
            print(f"Событие '{evt_name}': {len(df_evt)} записей")
    except Exception as e:
        print(f"⚠️ Ошибка получения доп. событий: {e}")

if __name__ == "__main__":
    main()
# src/metrics/utility.py
import pandas as pd
from demoparser2 import DemoParser as RawDemoParser


def calculate_utility_metrics(raw_parser: RawDemoParser) -> dict:
    """
    Возвращает словарь со статистикой Utility по каждому steamid:
    {
        "steamid": {
            "he_damage": float,
            "inferno_damage": float,
            "enemies_flashed": int,
            "flash_duration": float
        }
    }
    """
    stats = {}

    def _init_player(sid):
        if sid and sid not in stats:
            stats[sid] = {
                "he_damage": 0.0,
                "inferno_damage": 0.0,
                "enemies_flashed": 0,
                "flash_duration": 0.0,
            }

    # 1. Считаем урон от HE и Molotov/Incendiary через player_hurt
    try:
        hurt_events = raw_parser.parse_events(["player_hurt"])
        df_hurt = None
        if isinstance(hurt_events, pd.DataFrame):
            df_hurt = hurt_events
        elif isinstance(hurt_events, list) and len(hurt_events) > 0:
            df_hurt = hurt_events[0][1] if isinstance(hurt_events[0], tuple) else hurt_events[0]

        if df_hurt is not None and not df_hurt.empty:
            for _, row in df_hurt.iterrows():
                attacker = str(row.get("attacker_steamid", ""))
                weapon = str(row.get("weapon", "")).lower()
                dmg = float(row.get("dmg_health", 0))

                if not attacker or attacker == "0":
                    continue

                _init_player(attacker)

                if weapon in ["hegrenade"]:
                    stats[attacker]["he_damage"] += dmg
                elif weapon in ["inferno", "molotov", "incgrenade"]:
                    stats[attacker]["inferno_damage"] += dmg
    except Exception as e:
        print(f"⚠️ Ошибка при парсинге player_hurt: {e}")

    # 2. Считаем ослепления через player_blind
    try:
        blind_events = raw_parser.parse_events(["player_blind"])
        df_blind = None
        if isinstance(blind_events, pd.DataFrame):
            df_blind = blind_events
        elif isinstance(blind_events, list) and len(blind_events) > 0:
            df_blind = blind_events[0][1] if isinstance(blind_events[0], tuple) else blind_events[0]

        if df_blind is not None and not df_blind.empty:
            for _, row in df_blind.iterrows():
                attacker = str(row.get("attacker_steamid", ""))
                duration = float(row.get("blind_duration", 0.0))

                if not attacker or attacker == "0" or duration <= 0:
                    continue

                _init_player(attacker)
                stats[attacker]["enemies_flashed"] += 1
                stats[attacker]["flash_duration"] += duration
    except Exception as e:
        print(f"⚠️ Ошибка при парсинге player_blind: {e}")

    return stats
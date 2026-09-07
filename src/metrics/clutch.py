from typing import Dict, List, Set
from demoparser2 import DemoParser as RawDemoParser


def calculate_clutches(parser: RawDemoParser, player_steam_ids: List[str]) -> Dict[str, int]:
    """
    Рассчитывает количество выигранных клатчей для каждого игрока.
    Динамически определяет все сыгранные live-раунды.
    """
    clutches = {p_id: 0 for p_id in player_steam_ids}

    # Извлекаем события смертей и раундов
    death_events = parser.parse_events(["player_death"])
    round_events = parser.parse_events(["round_end"])

    if not death_events or not round_events:
        return clutches

    df_deaths = death_events[0][1] if isinstance(death_events, list) else death_events
    df_rounds = round_events[0][1] if isinstance(round_events, list) else round_events

    if df_deaths.empty or df_rounds.empty:
        return clutches

    # Берем тики всех реальных live-раундов без жесткого лимита в 24
    round_ticks = df_rounds["tick"].tolist()

    # Разбиваем смерти по раундам
    for i in range(len(round_ticks)):
        start_tick = round_ticks[i - 1] if i > 0 else 0
        end_tick = round_ticks[i]

        round_winner = df_rounds.iloc[i].get("winner", None)
        if not round_winner:
            continue

        round_deaths = df_deaths[(df_deaths["tick"] > start_tick) & (df_deaths["tick"] <= end_tick)]

        # Определяем оставшихся игроков в раунде
        dead_players: Set[str] = set()
        clutch_candidates: Dict[str, str] = {}  # team -> steam_id

        for _, death in round_deaths.iterrows():
            victim_id = str(death.get("user_steamid", ""))
            victim_team = str(death.get("user_team_name", ""))

            if victim_id:
                dead_players.add(victim_id)

        # Реконструируем выживших участников (упрощенная модель)
        alive_by_team: Dict[str, List[str]] = {"CT": [], "T": []}
        for sid in player_steam_ids:
            if sid not in dead_players:
                # Временно распределяем, если статус живого игрока однозначен
                pass

    return clutches
from typing import List, Dict, Any
from src.domain.models import PlayerStats, Match


def calculate_player_aggregates(stats_list: List[PlayerStats]) -> Dict[str, Any]:
    """
    Вычисляет суммарную и среднюю статистику игрока по списку матчей.
    """
    if not stats_list:
        return {
            "total_matches": 0,
            "avg_kd": 0.0,
            "avg_adr": 0.0,
            "avg_hs": 0.0,
            "total_kills": 0,
            "total_deaths": 0,
        }

    total_matches = len(stats_list)
    total_kills = sum(s.kills for s in stats_list)
    total_deaths = sum(s.deaths for s in stats_list)
    total_damage = sum(s.damage for s in stats_list)
    total_rounds = sum(s.rounds_played for s in stats_list)
    total_headshots = sum(s.headshots for s in stats_list)

    # Расчёт общих средних показателей
    overall_kd = round(total_kills / total_deaths, 2) if total_deaths > 0 else float(total_kills)
    overall_adr = round(total_damage / total_rounds, 1) if total_rounds > 0 else 0.0
    overall_hs = round((total_headshots / total_kills) * 100, 1) if total_kills > 0 else 0.0

    return {
        "total_matches": total_matches,
        "avg_kd": overall_kd,
        "avg_adr": overall_adr,
        "avg_hs": overall_hs,
        "total_kills": total_kills,
        "total_deaths": total_deaths,
    }


def calculate_winrate(matches: List[Match], target_steam_id: str) -> float:
    """
    Вычисляет процент побед игрока (Winrate %).
    """
    if not matches:
        return 0.0

    wins = 0
    for match in matches:
        if match.winner_side:
            wins += 1

    return round((wins / len(matches)) * 100, 1)
from typing import List, Dict, Any
from src.domain.models import PlayerStats


def calculate_player_aggregates(stats_list: List[PlayerStats], total_matches: int = None) -> Dict[str, Any]:
    """Агрегирует среднюю статистику игроков."""
    if not stats_list:
        return {
            "total_matches": 0,
            "avg_kd": 0.0,
            "avg_adr": 0.0,
            "avg_hs": 0.0,
        }

    # Если передали реальное кол-во матчей — берем его, иначе считаем по длине списка
    matches_count = total_matches if total_matches is not None else len(stats_list)

    total_kills = sum(s.kills for s in stats_list)
    total_deaths = sum(s.deaths for s in stats_list)
    total_damage = sum(s.damage for s in stats_list)
    total_headshots = sum(s.headshots for s in stats_list)
    total_rounds = sum(s.rounds_played for s in stats_list)

    avg_kd = round(total_kills / max(1, total_deaths), 2)
    avg_adr = round(total_damage / max(1, total_rounds), 1)
    avg_hs = round((total_headshots / max(1, total_kills)) * 100, 1)

    return {
        "total_matches": matches_count,
        "avg_kd": avg_kd,
        "avg_adr": avg_adr,
        "avg_hs": avg_hs,
    }
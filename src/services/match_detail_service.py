from typing import Dict, Any, List
from src.database.matches import get_match_by_id, get_match_players_stats


class MatchDetailService:
    """Сервис для сбора и агрегации детальной статистики по конкретному матчу."""

    @staticmethod
    def get_match_overview(match_id: str) -> Dict[str, Any]:
        match = get_match_by_id(match_id)
        if not match:
            return {}

        players_stats = get_match_players_stats(match_id)

        # Разделяем игроков по командам
        ct_players = [p for p in players_stats if p.get("team") == "CT"]
        t_players = [p for p in players_stats if p.get("team") == "T"]

        # Если team не разбит жестко на CT/T, сортируем по фрагам
        if not ct_players and not t_players:
            players_stats_sorted = sorted(players_stats, key=lambda x: x["kills"], reverse=True)
            half = len(players_stats_sorted) // 2
            ct_players = players_stats_sorted[:half]
            t_players = players_stats_sorted[half:]

        return {
            "match_id": match.match_id,
            "map_name": match.map_name,
            "played_at": match.played_at.strftime("%Y-%m-%d %H:%M") if hasattr(match.played_at, "strftime") else str(match.played_at),
            "score_ct": match.score_ct,
            "score_t": match.score_t,
            "winner_side": match.winner_side,
            "ct_players": ct_players,
            "t_players": t_players,
            "all_players": players_stats,
        }
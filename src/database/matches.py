from typing import List, Dict, Any, Optional
from sqlalchemy.orm import joinedload
from src.database.connection import get_db
from src.domain.models import Match, MatchPlayer


def save_match(match: Match) -> Optional[Match]:
    """Принимает объект Match (из DemoParser) и сохраняет его вместе с игроками в БД."""
    with get_db() as db:
        existing_match = db.query(Match).filter(Match.match_id == match.match_id).first()
        if existing_match:
            return existing_match

        # Пересчитываем ADR и % HS для каждого игрока перед записью
        for p in match.players:
            p.match_id = match.match_id
            rounds = max(1, p.rounds_played)
            kills = max(1, p.kills)
            p.adr = round(p.damage / rounds, 1)
            p.hs_percent = round((p.headshots / kills) * 100, 1)

        db.add(match)
        db.commit()
        db.refresh(match)
        return match


def get_all_matches() -> List[Match]:
    """Возвращает список всех сохраненных матчей сразу со списком игроков (joinedload)."""
    with get_db() as db:
        return (
            db.query(Match)
            .options(joinedload(Match.players))
            .order_by(Match.played_at.desc())
            .all()
        )


def get_match_by_id(match_id: str) -> Optional[Match]:
    """Возвращает объект конкретного матча по его match_id с предзагруженными игроками."""
    with get_db() as db:
        return (
            db.query(Match)
            .options(joinedload(Match.players))
            .filter(Match.match_id == match_id)
            .first()
        )


def get_player_history(player_name: str) -> List[Dict[str, Any]]:
    """Возвращает историю показателей конкретного игрока."""
    with get_db() as db:
        records = (
            db.query(MatchPlayer, Match)
            .join(Match, MatchPlayer.match_id == Match.match_id)
            .filter(MatchPlayer.name == player_name)
            .order_by(Match.played_at.asc())
            .all()
        )

        history = []
        for player, match in records:
            history.append({
                "match_id": match.match_id,
                "map_name": match.map_name,
                "played_at": match.played_at,
                "kills": player.kills,
                "deaths": player.deaths,
                "assists": player.assists,
                "kd": round(player.kills / max(1, player.deaths), 2),
                "adr": player.adr,
                "hs_percent": player.hs_percent,
                "rounds_played": player.rounds_played
            })

        return history


def get_match_players_stats(match_id: str) -> List[Dict[str, Any]]:
    """Возвращает статистику всех игроков выбранного матча."""
    with get_db() as db:
        players = db.query(MatchPlayer).filter(MatchPlayer.match_id == match_id).all()
        result = []
        for p in players:
            result.append({
                "steam_id": p.steam_id,
                "name": p.name,
                "kills": p.kills,
                "deaths": p.deaths,
                "assists": p.assists,
                "kd": round(p.kills / max(1, p.deaths), 2),
                "adr": p.adr,
                "hs_percent": p.hs_percent,
                "rounds_played": p.rounds_played
            })
        return result
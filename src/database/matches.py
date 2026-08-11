from typing import List, Dict, Any, Optional
from src.database.connection import get_db
from src.domain.models import Match, MatchPlayer


def save_match(match_data: Dict[str, Any], players_data: List[Dict[str, Any]]) -> Optional[Match]:
    """Сохраняет данные матча и его игроков в базу данных."""
    with get_db() as db:
        # Проверяем, не существует ли уже такой матч
        existing_match = db.query(Match).filter(Match.match_id == match_data.get("match_id")).first()
        if existing_match:
            return existing_match

        new_match = Match(
            match_id=match_data.get("match_id"),
            map_name=match_data.get("map_name"),
            played_at=match_data.get("played_at"),
            score_ct=match_data.get("score_ct", 0),
            score_t=match_data.get("score_t", 0),
            winner_side=match_data.get("winner_side", "UNKNOWN")
        )
        db.add(new_match)

        for p in players_data:
            player_record = MatchPlayer(
                match_id=match_data.get("match_id"),
                steam_id=p.get("steam_id"),
                name=p.get("name"),
                team_side=p.get("team_side", "ALL"),
                kills=p.get("kills", 0),
                deaths=p.get("deaths", 0),
                assists=p.get("assists", 0),
                adr=p.get("adr", 0.0),
                hs_percent=p.get("hs_percent", 0.0),
                first_kills=p.get("first_kills", 0),
                first_deaths=p.get("first_deaths", 0)
            )
            db.add(player_record)

        db.commit()
        db.refresh(new_match)
        return new_match


def get_all_matches() -> List[Match]:
    """Возвращает список всех сохраненных матчей."""
    with get_db() as db:
        return db.query(Match).order_by(Match.played_at.desc()).all()


def get_match_by_id(match_id: str) -> Optional[Match]:
    """Возвращает объект конкретного матча по его match_id."""
    with get_db() as db:
        return db.query(Match).filter(Match.match_id == match_id).first()


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
                "adr": round(player.adr, 1),
                "hs_percent": round(player.hs_percent, 1),
                "first_kills": getattr(player, "first_kills", 0),
                "first_deaths": getattr(player, "first_deaths", 0),
            })

        return history


def get_match_players_stats(match_id: str) -> List[Dict[str, Any]]:
    """Возвращает подробную статистику всех игроков выбранного матча."""
    with get_db() as db:
        players = db.query(MatchPlayer).filter(MatchPlayer.match_id == match_id).all()
        result = []
        for p in players:
            result.append({
                "steam_id": p.steam_id,
                "name": p.name,
                "team": getattr(p, "team_side", "ALL"),
                "kills": p.kills,
                "deaths": p.deaths,
                "assists": p.assists,
                "kd": round(p.kills / max(1, p.deaths), 2),
                "adr": round(p.adr, 1),
                "hs_percent": round(p.hs_percent, 1),
                "first_kills": getattr(p, "first_kills", 0),
                "first_deaths": getattr(p, "first_deaths", 0),
            })
        return result
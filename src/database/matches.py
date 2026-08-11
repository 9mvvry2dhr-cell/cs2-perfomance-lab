from sqlalchemy.orm import Session, joinedload
from src.database.connection import SessionLocal
from src.domain.models import Match, MatchPlayer
from src.domain.dto import ParsedMatch


def save_match(parsed_match: ParsedMatch) -> Match:
    """Принимает ParsedMatch (DTO), преобразует в ORM-модели и сохраняет в БД."""
    session: Session = SessionLocal()
    try:
        # 1. Создаем ORM объект Match из DTO
        match_orm = Match(
            id=parsed_match.match_id,
            map_name=parsed_match.map_name,
            duration_seconds=parsed_match.duration_seconds,
            rounds_played=parsed_match.rounds_played,
        )

        # 2. Создаем ORM объекты MatchPlayer из DTO
        for p in parsed_match.players:
            player_orm = MatchPlayer(
                match_id=parsed_match.match_id,
                steam_id=p.steam_id,
                name=p.name,
                kills=p.kills,
                deaths=p.deaths,
                assists=p.assists,
                damage=p.damage,
                headshots=p.headshots,
                rounds_played=p.rounds_played,
                adr=p.adr,
                hs_percent=p.hs_percent,
            )
            match_orm.players.append(player_orm)

        # 3. Сохраняем в БД
        session.merge(match_orm)
        session.commit()
        session.refresh(match_orm)
        return match_orm

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_all_matches():
    """Получает все матчи с предзагруженными игроками."""
    session: Session = SessionLocal()
    try:
        matches = (
            session.query(Match)
            .options(joinedload(Match.players))
            .order_by(Match.id.desc())
            .all()
        )
        return matches
    finally:
        session.close()


def get_match_by_id(match_id: str):
    """Получает конкретный матч по id."""
    session: Session = SessionLocal()
    try:
        match = (
            session.query(Match)
            .options(joinedload(Match.players))
            .filter(Match.id == match_id)
            .first()
        )
        return match
    finally:
        session.close()


def get_match_players_stats(match_id: str):
    """Получает статистику всех игроков конкретного матча."""
    session: Session = SessionLocal()
    try:
        players = (
            session.query(MatchPlayer)
            .filter(MatchPlayer.match_id == match_id)
            .all()
        )
        return players
    finally:
        session.close()


def get_player_history(steam_id: str):
    """Получает историю всех матчей конкретного игрока."""
    session: Session = SessionLocal()
    try:
        players_stats = (
            session.query(MatchPlayer)
            .filter(MatchPlayer.steam_id == steam_id)
            .all()
        )
        return players_stats
    finally:
        session.close()


def get_recent_matches(limit: int = 10):
    """Получает список последних N матчей."""
    session: Session = SessionLocal()
    try:
        matches = (
            session.query(Match)
            .order_by(Match.id.desc())
            .limit(limit)
            .all()
        )
        return matches
    finally:
        session.close()


def delete_match(match_id: str):
    """Удаляет матч из БД по его ID."""
    session: Session = SessionLocal()
    try:
        match = session.query(Match).filter(Match.id == match_id).first()
        if match:
            session.delete(match)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
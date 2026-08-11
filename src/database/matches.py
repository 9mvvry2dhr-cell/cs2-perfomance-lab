from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.database.connection import get_session
from src.domain.models import Match, PlayerStat, RoundStat
from src.domain.metrics import calculate_kd, calculate_adr, calculate_hs_percent
from src.parsing.dto import ParsedMatch


def save_match(parsed_match: ParsedMatch) -> Optional[Match]:
    """Сохраняет матч, игроков и раунды в БД без применения fake-fallback раундов."""
    with get_session() as session:
        existing = session.scalar(
            select(Match).where(Match.match_id == parsed_match.match_id)
        )
        if existing:
            return existing

        match = Match(
            match_id=parsed_match.match_id,
            map_name=parsed_match.map_name,
            played_at=parsed_match.played_at,
            score_ct=parsed_match.score_ct,
            score_t=parsed_match.score_t,
            rounds_played=parsed_match.rounds_played,
            winner_side=parsed_match.winner_side,
            is_valid=parsed_match.is_valid,
            validation_error=parsed_match.validation_error
        )

        for p in parsed_match.players:
            # Расчет метрик выполняется ТОЛЬКО при валидных раундах
            if parsed_match.is_valid and parsed_match.rounds_played > 0:
                kd_val = calculate_kd(p.kills, p.deaths)
                adr_val = calculate_adr(p.damage, parsed_match.rounds_played)
                hs_val = calculate_hs_percent(p.headshots, p.kills)
            else:
                kd_val, adr_val, hs_val = None, None, None

            player_stat = PlayerStat(
                steam_id=p.steam_id,
                name=p.name,
                team=p.team,
                kills=p.kills,
                deaths=p.deaths,
                assists=p.assists,
                damage=p.damage,
                headshots=p.headshots,
                rounds_played=p.rounds_played,
                kd=kd_val,
                adr=adr_val,
                hs_percent=hs_val,
                first_kills=p.first_kills,
                first_deaths=p.first_deaths,
            )
            match.players.append(player_stat)

        for r in parsed_match.rounds:
            round_stat = RoundStat(
                round_num=r.round_num,
                winner_side=r.winner_side,
                win_reason=r.win_reason,
                end_tick=r.end_tick
            )
            match.rounds.append(round_stat)

        session.add(match)
        session.commit()
        return match


def get_all_matches() -> List[Match]:
    """Возвращает список всех матчей вместе со связанными игроками и раундами."""
    with get_session() as session:
        stmt = (
            select(Match)
            .options(joinedload(Match.players), joinedload(Match.rounds))
            .order_by(Match.played_at.desc())
        )
        return list(session.scalars(stmt).unique().all())


def get_match_by_id(match_id: str) -> Optional[Match]:
    """Возвращает матч по ID вместе со статистикой."""
    with get_session() as session:
        stmt = (
            select(Match)
            .options(joinedload(Match.players), joinedload(Match.rounds))
            .where(Match.match_id == match_id)
        )
        return session.scalar(stmt)


def get_match_players_stats(match_id: str) -> List[Dict[str, Any]]:
    """Возвращает статистику игроков матча в виде словарей."""
    with get_session() as session:
        stmt = select(PlayerStat).where(PlayerStat.match_id == match_id)
        players = session.scalars(stmt).all()

        return [
            {
                "steam_id": p.steam_id,
                "name": p.name,
                "team": p.team,
                "kills": p.kills,
                "deaths": p.deaths,
                "assists": p.assists,
                "damage": p.damage,
                "headshots": p.headshots,
                "rounds_played": p.rounds_played,
                "kd": p.kd,
                "adr": p.adr,
                "hs_percent": p.hs_percent,
                "first_kills": p.first_kills,
                "first_deaths": p.first_deaths,
            }
            for p in players
        ]


def get_player_history(steam_id: str) -> List[Dict[str, Any]]:
    """Поиск истории игрока строго по SteamID (Identity)."""
    with get_session() as session:
        stmt = (
            select(PlayerStat, Match)
            .join(Match, PlayerStat.match_id == Match.match_id)
            .where(PlayerStat.steam_id == steam_id)
            .order_by(Match.played_at.asc())
        )
        results = session.execute(stmt).all()

        return [
            {
                "match_id": match.match_id,
                "map_name": match.map_name,
                "played_at": match.played_at,
                "kills": stat.kills or 0,
                "deaths": stat.deaths or 0,
                "assists": stat.assists or 0,
                "damage": stat.damage or 0.0,
                "headshots": stat.headshots or 0,
                "rounds_played": stat.rounds_played or 0,
                "kd": stat.kd,
                "adr": stat.adr,
                "hs_percent": stat.hs_percent,
                "first_kills": stat.first_kills or 0,
                "first_deaths": stat.first_deaths or 0,
            }
            for stat, match in results
        ]
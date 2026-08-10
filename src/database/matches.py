from typing import List, Optional
from datetime import datetime
from src.database.connection import get_connection
from src.domain.models import Match, PlayerStats


def save_match(match: Match) -> None:
    """Сохраняет матч и статистику всех его игроков в БД."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Сохраняем матч
        cursor.execute("""
            INSERT OR REPLACE INTO matches 
            (match_id, map_name, played_at, duration_seconds, score_ct, score_t, winner_side)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            match.match_id,
            match.map_name,
            match.played_at.isoformat(),
            match.duration_seconds,
            match.score_ct,
            match.score_t,
            match.winner_side
        ))

        # Сохраняем игроков
        for p in match.players:
            cursor.execute("""
                INSERT INTO player_stats 
                (match_id, steam_id, name, kills, deaths, assists, damage, headshots, 
                 rounds_played, first_kills, first_deaths, flash_assists, utility_damage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match.match_id, p.steam_id, p.name, p.kills, p.deaths, p.assists,
                p.damage, p.headshots, p.rounds_played, p.first_kills, p.first_deaths,
                p.flash_assists, p.utility_damage
            ))

        conn.commit()


def get_all_matches() -> List[Match]:
    """Загружает список всех сохранённых матчей из БД."""
    matches = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches ORDER BY played_at DESC")
        rows = cursor.fetchall()

        for row in rows:
            match = Match(
                match_id=row["match_id"],
                map_name=row["map_name"],
                played_at=datetime.fromisoformat(row["played_at"]),
                duration_seconds=row["duration_seconds"],
                score_ct=row["score_ct"],
                score_t=row["score_t"],
                winner_side=row["winner_side"]
            )
            matches.append(match)

    return matches
from typing import List
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
    """Загружает список всех сохранённых матчей из БД вместе с игроками."""
    matches = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches ORDER BY played_at DESC")
        rows = cursor.fetchall()

        for row in rows:
            # Загружаем игроков для данного матча
            cursor.execute("SELECT * FROM player_stats WHERE match_id = ?", (row["match_id"],))
            p_rows = cursor.fetchall()
            
            players = []
            for p in p_rows:
                players.append(PlayerStats(
                    steam_id=p["steam_id"],
                    name=p["name"],
                    kills=p["kills"],
                    deaths=p["deaths"],
                    assists=p["assists"],
                    damage=p["damage"],
                    headshots=p["headshots"],
                    rounds_played=p["rounds_played"],
                    first_kills=p["first_kills"],
                    first_deaths=p["first_deaths"],
                    flash_assists=p["flash_assists"],
                    utility_damage=p["utility_damage"]
                ))

            match = Match(
                match_id=row["match_id"],
                map_name=row["map_name"],
                played_at=datetime.fromisoformat(row["played_at"]),
                duration_seconds=row["duration_seconds"],
                score_ct=row["score_ct"],
                score_t=row["score_t"],
                winner_side=row["winner_side"],
                players=players
            )
            matches.append(match)

    return matches
def get_player_history(name_or_steam_id: str) -> List[dict]:
    """Возвращает хронологическую историю всех матчей игрока для построения графиков."""
    history = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                m.match_id,
                m.map_name,
                m.played_at,
                p.kills,
                p.deaths,
                p.damage,
                p.headshots,
                p.rounds_played
            FROM player_stats p
            JOIN matches m ON p.match_id = m.match_id
            WHERE p.name = ? OR p.steam_id = ?
            ORDER BY m.played_at ASC
        """, (name_or_steam_id, name_or_steam_id))
        
        rows = cursor.fetchall()
        for r in rows:
            rounds = max(1, r["rounds_played"])
            deaths = max(1, r["deaths"])
            
            history.append({
                "match_id": r["match_id"],
                "map_name": r["map_name"],
                "played_at": r["played_at"],
                "kd": round(r["kills"] / deaths, 2),
                "adr": round(r["damage"] / rounds, 1),
                "hs_percent": round((r["headshots"] / max(1, r["kills"])) * 100, 1),
                "kills": r["kills"],
                "deaths": r["deaths"],
                "rounds": rounds
            })
            
    return history

import sqlite3
from src.config.settings import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Возвращает объект подключения к базе данных SQLite."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Возвращает строки в виде словарей
    return conn


def init_db() -> None:
    """Инициализирует структуры таблиц в базе данных."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Таблица матчей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                map_name TEXT NOT NULL,
                played_at TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                score_ct INTEGER DEFAULT 0,
                score_t INTEGER DEFAULT 0,
                winner_side TEXT DEFAULT ''
            )
        """)

        # Таблица статистики игроков в матче
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                steam_id TEXT NOT NULL,
                name TEXT NOT NULL,
                kills INTEGER DEFAULT 0,
                deaths INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                damage INTEGER DEFAULT 0,
                headshots INTEGER DEFAULT 0,
                rounds_played INTEGER DEFAULT 0,
                first_kills INTEGER DEFAULT 0,
                first_deaths INTEGER DEFAULT 0,
                flash_assists INTEGER DEFAULT 0,
                utility_damage INTEGER DEFAULT 0,
                FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE
            )
        """)
        conn.commit()
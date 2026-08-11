from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.database.models import MatchModel, PlayerModel


class PlayerAnalyticsService:

    def __init__(self, session: Session):
        self.session = session

    def get_player_summary(self, steam_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает агрегированную статистику игрока по всем сохраненным матчам."""
        players_records = (
            self.session.query(PlayerModel, MatchModel)
            .join(MatchModel, PlayerModel.match_id == MatchModel.match_id)
            .filter(PlayerModel.steam_id == steam_id)
            .all()
        )

        if not players_records:
            return None

        total_matches = len(players_records)
        total_kills = 0
        total_deaths = 0
        total_assists = 0
        total_damage = 0.0
        total_rounds = 0
        total_he_dmg = 0.0
        total_molotov_dmg = 0.0
        total_flashed = 0
        total_flash_sec = 0.0
        total_entry_kills = 0
        total_entry_deaths = 0
        total_clutches = 0
        latest_nickname = ""

        for p, m in players_records:
            latest_nickname = p.name
            total_kills += p.kills
            total_deaths += p.deaths
            total_assists += p.assists
            total_damage += p.damage
            total_rounds += m.rounds_played
            total_he_dmg += p.he_damage
            total_molotov_dmg += p.inferno_damage
            total_flashed += p.enemies_flashed
            total_flash_sec += p.flash_duration
            total_entry_kills += p.entry_kills
            total_entry_deaths += p.entry_deaths
            total_clutches += p.clutches_won

        kd_ratio = total_kills / max(1, total_deaths)
        avg_adr = total_damage / max(1, total_rounds)
        entry_kd = total_entry_kills / max(1, total_entry_deaths)

        return {
            "steam_id": steam_id,
            "nickname": latest_nickname,
            "matches_played": total_matches,
            "rounds_played": total_rounds,
            "kd_ratio": round(kd_ratio, 2),
            "avg_adr": round(avg_adr, 1),
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "total_assists": total_assists,
            "total_he_damage": round(total_he_dmg, 0),
            "total_molotov_damage": round(total_molotov_dmg, 0),
            "total_enemies_flashed": total_flashed,
            "total_flash_duration": round(total_flash_sec, 1),
            "entry_kills": total_entry_kills,
            "entry_deaths": total_entry_deaths,
            "entry_kd": round(entry_kd, 2),
            "clutches_won": total_clutches,
        }
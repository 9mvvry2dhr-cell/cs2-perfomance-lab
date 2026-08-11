from sqlalchemy.orm import Session
from src.parsing.dto import ParsedMatch
from src.database.models import MatchModel, PlayerModel, RoundModel

class MatchRepository:

    def __init__(self, session: Session):
        self.session = session

    def save_match(self, parsed_match: ParsedMatch) -> bool:
        """Сохраняет распаршенный матч в базу данных (или перезаписывает, если существует)."""
        # Удаляем существующий матч с таким id, если он был загружен ранее
        existing = self.session.query(MatchModel).filter_by(match_id=parsed_match.match_id).first()
        if existing:
            self.session.delete(existing)
            self.session.flush()

        match_entry = MatchModel(
            match_id=parsed_match.match_id,
            map_name=parsed_match.map_name,
            duration_seconds=parsed_match.duration_seconds,
            rounds_played=parsed_match.rounds_played,
            score_ct=parsed_match.score_ct,
            score_t=parsed_match.score_t,
            winner_side=parsed_match.winner_side,
            is_valid=parsed_match.is_valid,
        )

        for p in parsed_match.players:
            player_entry = PlayerModel(
                steam_id=p.steam_id,
                name=p.name,
                kills=p.kills,
                deaths=p.deaths,
                assists=p.assists,
                damage=p.damage,
                headshots=p.headshots,
                he_damage=p.he_damage,
                inferno_damage=p.inferno_damage,
                enemies_flashed=p.enemies_flashed,
                flash_duration=p.flash_duration,
                entry_kills=p.entry_kills,
                entry_deaths=p.entry_deaths,
                clutches_won=p.clutches_won,
            )
            match_entry.players.append(player_entry)

        for r in parsed_match.rounds:
            round_entry = RoundModel(
                round_num=r.round_num,
                winner_side=r.winner_side,
                win_reason=r.win_reason,
                end_tick=r.end_tick,
            )
            match_entry.rounds.append(round_entry)

        self.session.add(match_entry)
        self.session.commit()
        return True
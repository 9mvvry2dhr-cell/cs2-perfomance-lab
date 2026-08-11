from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class MatchModel(Base):
    __tablename__ = "matches"

    match_id = Column(String, primary_key=True)
    map_name = Column(String, nullable=False)
    duration_seconds = Column(Integer, default=0)
    rounds_played = Column(Integer, default=0)
    score_ct = Column(Integer, default=0)
    score_t = Column(Integer, default=0)
    winner_side = Column(String, default="UNKNOWN")
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    players = relationship("PlayerModel", back_populates="match", cascade="all, delete-orphan")
    rounds = relationship("RoundModel", back_populates="match", cascade="all, delete-orphan")


class PlayerModel(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.match_id"), nullable=False)
    steam_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    damage = Column(Float, default=0.0)
    headshots = Column(Integer, default=0)
    
    # Utility & Entry & Clutches
    he_damage = Column(Float, default=0.0)
    inferno_damage = Column(Float, default=0.0)
    enemies_flashed = Column(Integer, default=0)
    flash_duration = Column(Float, default=0.0)
    entry_kills = Column(Integer, default=0)
    entry_deaths = Column(Integer, default=0)
    clutches_won = Column(Integer, default=0)

    match = relationship("MatchModel", back_populates="players")


class RoundModel(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.match_id"), nullable=False)
    round_num = Column(Integer, nullable=False)
    winner_side = Column(String, nullable=False)
    win_reason = Column(String, default="unknown")
    end_tick = Column(Integer, default=0)

    match = relationship("MatchModel", back_populates="rounds")
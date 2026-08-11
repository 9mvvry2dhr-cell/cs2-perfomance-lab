from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.connection import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, unique=True, index=True, nullable=False)
    map_name = Column(String, nullable=False)
    played_at = Column(DateTime, default=datetime.utcnow)
    score_ct = Column(Integer, default=0)
    score_t = Column(Integer, default=0)
    winner_side = Column(String, default="UNKNOWN")

    players = relationship("MatchPlayer", back_populates="match", cascade="all, delete-orphan")


class MatchPlayer(Base):
    __tablename__ = "match_players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.match_id"), nullable=False)
    steam_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    team_side = Column(String, default="ALL")
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    adr = Column(Float, default=0.0)
    hs_percent = Column(Float, default=0.0)
    first_kills = Column(Integer, default=0)
    first_deaths = Column(Integer, default=0)

    match = relationship("Match", back_populates="players")


# Алиас для обеспечения обратной совместимости с demo_parser.py
PlayerStats = MatchPlayer
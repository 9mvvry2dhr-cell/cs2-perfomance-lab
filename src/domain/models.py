from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Match(Base):
    __tablename__ = "matches"

    match_id = Column(String, primary_key=True)
    map_name = Column(String(50), nullable=False)
    duration_seconds = Column(Integer, default=0)
    rounds_played = Column(Integer, default=0)
    score_ct = Column(Integer, default=0)
    score_t = Column(Integer, default=0)
    winner_side = Column(String(10), default="UNKNOWN")
    played_at = Column(DateTime, default=datetime.now)

    # Связи
    players = relationship("PlayerStat", back_populates="match", cascade="all, delete-orphan")
    rounds = relationship("RoundStat", back_populates="match", cascade="all, delete-orphan")


class PlayerStat(Base):
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    team = Column(String(10), nullable=True)
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    kd = Column(Float, default=0.0)
    adr = Column(Float, default=0.0)
    hs_percent = Column(Float, default=0.0)
    first_kills = Column(Integer, default=0)
    first_deaths = Column(Integer, default=0)

    match = relationship("Match", back_populates="players")


class RoundStat(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False)
    round_num = Column(Integer, nullable=False)
    winner_side = Column(String(10), nullable=False)
    win_reason = Column(String(50), nullable=True)
    end_tick = Column(Integer, default=0)

    match = relationship("Match", back_populates="rounds")
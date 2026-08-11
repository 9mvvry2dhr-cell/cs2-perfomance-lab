from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""
    pass


class Match(Base):
    """Модель матча CS2."""
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    map_name: Mapped[str] = mapped_column(String(64), nullable=False)
    played_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    score_ct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_t: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rounds_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winner_side: Mapped[str] = mapped_column(String(10), nullable=False)

    # Связь один-ко-многим с игроками
    players: Mapped[List["PlayerStat"]] = relationship(
        "PlayerStat", 
        back_populates="match", 
        cascade="all, delete-orphan"
    )


class PlayerStat(Base):
    """Модель индивидуальной статистики игрока за матч."""
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        String(64), 
        ForeignKey("matches.match_id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    team: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    kills: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    adr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hs_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    first_kills: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_deaths: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="players")
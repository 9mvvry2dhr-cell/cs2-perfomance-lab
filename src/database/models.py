from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MatchModel(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )
    map_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    rounds_played: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    score_ct: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    score_t: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    winner_side: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    validation_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    analysis_version: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="v1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    players: Mapped[list["MatchPlayerModel"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchPlayerModel.position",
    )


class MatchPlayerModel(Base):
    __tablename__ = "match_players"

    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "steam_id",
            name="uq_match_players_match_steam",
        ),
        UniqueConstraint(
            "match_id",
            "position",
            name="uq_match_players_match_position",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    match_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "matches.match_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # MatchAnalysis.players is an ordered list.
    # Persisting position lets DB -> contract reproduce it exactly.
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    steam_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    # PlayerStats
    rounds_played: Mapped[int] = mapped_column(Integer, nullable=False)
    kills: Mapped[int] = mapped_column(Integer, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, nullable=False)
    headshots: Mapped[int] = mapped_column(Integer, nullable=False)
    damage: Mapped[float] = mapped_column(Float, nullable=False)

    kd: Mapped[float] = mapped_column(Float, nullable=False)
    adr: Mapped[float] = mapped_column(Float, nullable=False)
    headshot_pct: Mapped[float] = mapped_column(Float, nullable=False)

    kast_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    kast_pct: Mapped[float] = mapped_column(Float, nullable=False)

    survived_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    survival_pct: Mapped[float] = mapped_column(Float, nullable=False)

    entry_kills: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_deaths: Mapped[int] = mapped_column(Integer, nullable=False)

    he_damage: Mapped[float] = mapped_column(Float, nullable=False)
    inferno_damage: Mapped[float] = mapped_column(Float, nullable=False)
    enemies_flashed: Mapped[int] = mapped_column(Integer, nullable=False)
    flash_duration: Mapped[float] = mapped_column(Float, nullable=False)

    clutches_won: Mapped[int] = mapped_column(Integer, nullable=False)
    trade_kills: Mapped[int] = mapped_column(Integer, nullable=False)
    traded_deaths: Mapped[int] = mapped_column(Integer, nullable=False)

    two_k_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    three_k_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    four_k_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    five_k_rounds: Mapped[int] = mapped_column(Integer, nullable=False)

    match: Mapped["MatchModel"] = relationship(
        back_populates="players",
    )

    sides: Mapped[list["PlayerSideStatsModel"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
    )

    findings: Mapped[list["FindingModel"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        order_by="FindingModel.position",
    )


class PlayerSideStatsModel(Base):
    __tablename__ = "player_side_stats"

    __table_args__ = (
        UniqueConstraint(
            "match_player_id",
            "side",
            name="uq_player_side_stats_player_side",
        ),
        CheckConstraint(
            "side IN ('CT', 'T')",
            name="ck_player_side_stats_side",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    match_player_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "match_players.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    side: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    # SideStats
    rounds_played: Mapped[int] = mapped_column(Integer, nullable=False)
    kills: Mapped[int] = mapped_column(Integer, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, nullable=False)
    damage: Mapped[float] = mapped_column(Float, nullable=False)
    adr: Mapped[float] = mapped_column(Float, nullable=False)

    kast_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    kast_pct: Mapped[float] = mapped_column(Float, nullable=False)

    survived_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    survival_pct: Mapped[float] = mapped_column(Float, nullable=False)

    entry_kills: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_deaths: Mapped[int] = mapped_column(Integer, nullable=False)

    player: Mapped["MatchPlayerModel"] = relationship(
        back_populates="sides",
    )


class FindingModel(Base):
    __tablename__ = "findings"

    __table_args__ = (
        UniqueConstraint(
            "match_player_id",
            "position",
            name="uq_findings_player_position",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    match_player_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "match_players.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Findings are deterministic and ordered in Analysis Contract v1.
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    side: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    player: Mapped["MatchPlayerModel"] = relationship(
        back_populates="findings",
    )

class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_analysis_jobs_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="queued",
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    file_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    match_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey(
            "matches.match_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

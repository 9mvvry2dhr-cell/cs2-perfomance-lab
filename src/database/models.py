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
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


ACTIVE_ANALYSIS_OWNER_INDEX = (
    "uq_analysis_jobs_active_owner"
)

ACTIVE_ANALYSIS_OWNER_PREDICATE = (
    "owner_steam_id IS NOT NULL "
    "AND status IN ('queued', 'processing')"
)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    steam_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    ai_overview_last_generated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ai_overview_last_response: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    sessions: Mapped[
        list["AuthSessionModel"]
    ] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class FoundingTesterModel(Base):
    __tablename__ = "founding_testers"

    __table_args__ = (
        CheckConstraint(
            "number BETWEEN 1 AND 10",
            name="ck_founding_testers_number",
        ),
        CheckConstraint(
            "premium_days >= 0",
            name="ck_founding_testers_premium_days",
        ),
    )

    number: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    steam_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey(
            "users.steam_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        unique=True,
        index=True,
    )

    awarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    premium_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
    )


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    steam_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey(
            "users.steam_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user: Mapped["UserModel"] = relationship(
        back_populates="sessions",
    )


class SiteVisitorModel(Base):
    __tablename__ = "site_visitors"

    visitor_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
        index=True,
    )


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

    findings_version: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="v2",
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

    round_advantages: Mapped[
        list["RoundAdvantageModel"]
    ] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="RoundAdvantageModel.round_num",
    )

    round_state_transitions: Mapped[
        list["RoundStateTransitionModel"]
    ] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by=(
            "RoundStateTransitionModel.round_num, "
            "RoundStateTransitionModel.position"
        ),
    )

    match_flow: Mapped[
        list["MatchFlowModel"]
    ] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchFlowModel.round_num",
    )

    turning_rounds: Mapped[
        list["TurningRoundModel"]
    ] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="TurningRoundModel.round_num",
    )

    turning_control_events: Mapped[
        list["TurningControlEventModel"]
    ] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by=(
            "TurningControlEventModel.round_num, "
            "TurningControlEventModel.position"
        ),
    )



class UserMatchModel(Base):
    __tablename__ = "user_matches"

    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "player_position",
            name="uq_user_matches_match_position",
        ),
        CheckConstraint(
            "player_position >= 0",
            name="ck_user_matches_player_position",
        ),
        CheckConstraint(
            "match_source IN ('premier', 'faceit', 'unknown')",
            name="ck_user_matches_match_source",
        ),
        Index(
            "ix_user_matches_match_id",
            "match_id",
        ),
        Index(
            "ix_user_matches_created_at",
            "created_at",
        ),
    )

    owner_steam_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey(
            "users.steam_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )

    match_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "matches.match_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )

    player_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    match_source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )

    ai_explanation_generated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ai_explanation_version: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    ai_explanation_response: Mapped[
        dict[str, Any] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
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
        CheckConstraint(
            "result IN ('win', 'loss', 'draw', 'unknown')",
            name="ck_match_players_result",
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

    result: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="unknown",
        server_default="unknown",
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

    clutch_attempts: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    clutches_won: Mapped[int] = mapped_column(Integer, nullable=False)
    trade_opportunities: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
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

    match_story: Mapped[
        list["MatchStoryEventModel"]
    ] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        order_by="MatchStoryEventModel.position",
    )


class MatchStoryEventModel(Base):
    __tablename__ = "match_story_events"

    __table_args__ = (
        UniqueConstraint(
            "match_player_id",
            "position",
            name="uq_match_story_player_position",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_match_story_position",
        ),
        CheckConstraint(
            "round_num >= 1",
            name="ck_match_story_round_num",
        ),
        CheckConstraint(
            "event_type IN ('highlight', 'growth', 'key')",
            name="ck_match_story_event_type",
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

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    round_num: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    player: Mapped["MatchPlayerModel"] = relationship(
        back_populates="match_story",
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
        CheckConstraint(
            "kind IN ('strength', 'weakness')",
            name="ck_findings_kind",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_findings_severity",
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
    kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(16),
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

class BugReportModel(Base):
    __tablename__ = "bug_reports"

    __table_args__ = (
        CheckConstraint(
            "category IN "
            "('analysis', 'statistics', 'ai', 'ui', 'other')",
            name="ck_bug_reports_category",
        ),
        Index(
            "ix_bug_reports_owner_steam_id",
            "owner_steam_id",
        ),
        Index(
            "ix_bug_reports_created_at",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    owner_steam_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey(
            "users.steam_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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

    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "analysis_jobs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )


class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_analysis_jobs_status",
        ),
        CheckConstraint(
            "match_source IN ('premier', 'faceit', 'unknown')",
            name="ck_analysis_jobs_match_source",
        ),
        Index(
            ACTIVE_ANALYSIS_OWNER_INDEX,
            "owner_steam_id",
            unique=True,
            postgresql_where=text(
                ACTIVE_ANALYSIS_OWNER_PREDICATE
            ),
            sqlite_where=text(
                ACTIVE_ANALYSIS_OWNER_PREDICATE
            ),
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

    owner_steam_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey(
            "users.steam_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    match_source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="unknown",
        server_default="unknown",
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


class RoundAdvantageModel(Base):
    __tablename__ = "round_advantages"

    __table_args__ = (
        CheckConstraint(
            "round_num >= 1",
            name="ck_round_advantages_round_num",
        ),
        CheckConstraint(
            "winner_team IN (2, 3)",
            name="ck_round_advantages_winner_team",
        ),
        CheckConstraint(
            "first_advantage_team IS NULL "
            "OR first_advantage_team IN (2, 3)",
            name="ck_round_advantages_first_team",
        ),
        CheckConstraint(
            "comeback_team IS NULL "
            "OR comeback_team IN (2, 3)",
            name="ck_round_advantages_comeback_team",
        ),
        CheckConstraint(
            "first_advantage_player_position IS NULL "
            "OR first_advantage_player_position >= 0",
            name="ck_round_advantages_player_position",
        ),
    )

    match_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "matches.match_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    round_num: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    winner_team: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    first_advantage_team: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    first_advantage_tick: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    first_advantage_player_position: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    converted_first_advantage: Mapped[
        bool | None
    ] = mapped_column(
        Boolean,
        nullable=True,
    )

    advantage_lost: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    advantage_restored: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    comeback_team: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    max_t_advantage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    max_ct_advantage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    match: Mapped["MatchModel"] = relationship(
        back_populates="round_advantages",
    )


class RoundStateTransitionModel(Base):
    __tablename__ = "round_state_transitions"

    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "round_num",
            "position",
            name="uq_round_state_match_round_position",
        ),
        CheckConstraint(
            "round_num >= 1",
            name="ck_round_state_round_num",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_round_state_position",
        ),
        CheckConstraint(
            "tick >= 0",
            name="ck_round_state_tick",
        ),
        CheckConstraint(
            "cause IN "
            "('enemy', 'world', 'suicide', "
            "'teamkill', 'unknown')",
            name="ck_round_state_cause",
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

    round_num: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    tick: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    attacker_position: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    victim_position: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    attacker_team: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    victim_team: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cause: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    t_alive_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ct_alive_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    t_alive_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ct_alive_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    match: Mapped["MatchModel"] = relationship(
        back_populates="round_state_transitions",
    )


class MatchFlowModel(Base):
    __tablename__ = "match_flow"

    __table_args__ = (
        CheckConstraint(
            "round_num >= 1",
            name="ck_match_flow_round_num",
        ),
        CheckConstraint(
            "winner_team IN ('team_a', 'team_b')",
            name="ck_match_flow_winner_team",
        ),
        CheckConstraint(
            "winner_side IN ('T', 'CT')",
            name="ck_match_flow_winner_side",
        ),
        CheckConstraint(
            "score_a_before >= 0 "
            "AND score_b_before >= 0 "
            "AND score_a_after >= 0 "
            "AND score_b_after >= 0",
            name="ck_match_flow_scores",
        ),
    )

    match_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "matches.match_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    round_num: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    winner_team: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    winner_side: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
    )

    score_a_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_b_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_a_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_b_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    match: Mapped["MatchModel"] = relationship(
        back_populates="match_flow",
    )


class TurningRoundModel(Base):
    __tablename__ = "turning_rounds"

    __table_args__ = (
        CheckConstraint(
            "round_num >= 1",
            name="ck_turning_rounds_round_num",
        ),
        CheckConstraint(
            "winner_team IN ('team_a', 'team_b')",
            name="ck_turning_rounds_winner_team",
        ),
        CheckConstraint(
            "swing_type IN ("
            "'no_advantage', "
            "'clean_conversion', "
            "'regained', "
            "'comeback', "
            "'stolen', "
            "'swing'"
            ")",
            name="ck_turning_rounds_swing_type",
        ),
        CheckConstraint(
            "score_a_before >= 0 "
            "AND score_b_before >= 0 "
            "AND score_a_after >= 0 "
            "AND score_b_after >= 0",
            name="ck_turning_rounds_scores",
        ),
        CheckConstraint(
            "opponent_streak_before >= 0",
            name="ck_turning_rounds_opponent_streak",
        ),
        CheckConstraint(
            "winner_run_length >= 1",
            name="ck_turning_rounds_run_length",
        ),
        CheckConstraint(
            "resolution IN ("
            "'sustained_control', "
            "'final_elimination', "
            "'unresolved'"
            ")",
            name="ck_turning_rounds_resolution",
        ),
        CheckConstraint(
            "decisive_tick IS NULL "
            "OR decisive_tick >= 0",
            name="ck_turning_rounds_decisive_tick",
        ),
    )

    match_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "matches.match_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    round_num: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    winner_team: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    swing_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    score_a_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_b_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_a_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_b_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    opponent_streak_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    winner_run_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reasons: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    resolution: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    decisive_tick: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    match: Mapped["MatchModel"] = relationship(
        back_populates="turning_rounds",
    )


class TurningControlEventModel(Base):
    __tablename__ = "turning_control_events"

    __table_args__ = (
        ForeignKeyConstraint(
            [
                "match_id",
                "round_num",
                "round_state_position",
            ],
            [
                "round_state_transitions.match_id",
                "round_state_transitions.round_num",
                "round_state_transitions.position",
            ],
            deferrable=True,
            initially="DEFERRED",
            name=(
                "fk_turning_control_"
                "round_state_transition"
            ),
        ),
        UniqueConstraint(
            "match_id",
            "round_num",
            "position",
            name=(
                "uq_turning_control_"
                "match_round_position"
            ),
        ),
        CheckConstraint(
            "round_num >= 1",
            name="ck_turning_control_round_num",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_turning_control_position",
        ),
        CheckConstraint(
            "round_state_position >= 0",
            name=(
                "ck_turning_control_"
                "round_state_position"
            ),
        ),
        CheckConstraint(
            "event_type IN ("
            "'control_gain', "
            "'control_loss', "
            "'reversal', "
            "'equalizer'"
            ")",
            name="ck_turning_control_event_type",
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

    round_num: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    round_state_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    decisive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    match: Mapped["MatchModel"] = relationship(
        back_populates="turning_control_events",
    )


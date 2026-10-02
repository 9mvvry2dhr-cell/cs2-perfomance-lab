"""add match story events

Revision ID: d2e4f6a8c1b3
Revises: a9c2e4f6b8d1
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e4f6a8c1b3"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a9c2e4f6b8d1"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "match_story_events",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "match_player_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "round_num",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "score",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            sa.JSON(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_player_id"],
            ["match_players.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "match_player_id",
            "position",
            name="uq_match_story_player_position",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_match_story_position",
        ),
        sa.CheckConstraint(
            "round_num >= 1",
            name="ck_match_story_round_num",
        ),
        sa.CheckConstraint(
            "event_type IN ('highlight', 'growth', 'key')",
            name="ck_match_story_event_type",
        ),
    )

    op.create_index(
        "ix_match_story_events_match_player_id",
        "match_story_events",
        ["match_player_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_match_story_events_match_player_id",
        table_name="match_story_events",
    )

    op.drop_table(
        "match_story_events"
    )

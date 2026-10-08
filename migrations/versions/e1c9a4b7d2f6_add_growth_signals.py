"""add growth signals

Revision ID: e1c9a4b7d2f6
Revises: d4f7b2c9a1e6
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa


revision = "e1c9a4b7d2f6"
down_revision = "d4f7b2c9a1e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "growth_signals",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
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
            "code",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            sa.JSON(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name=(
                "ck_growth_signals_"
                "position"
            ),
        ),
        sa.CheckConstraint(
            "kind IN "
            "('growth', 'strength', "
            "'neutral', 'insufficient')",
            name=(
                "ck_growth_signals_kind"
            ),
        ),
        sa.CheckConstraint(
            "confidence IN "
            "('none', 'low', "
            "'medium', 'high')",
            name=(
                "ck_growth_signals_"
                "confidence"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["match_player_id"],
            ["match_players.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "match_player_id",
            "position",
            name=(
                "uq_growth_signals_"
                "player_position"
            ),
        ),
    )

    op.create_index(
        "ix_growth_signals_match_player_id",
        "growth_signals",
        ["match_player_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_growth_signals_match_player_id",
        table_name="growth_signals",
    )

    op.drop_table(
        "growth_signals"
    )

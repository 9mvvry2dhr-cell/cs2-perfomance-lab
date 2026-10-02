"""add founding tester slots

Revision ID: b7d3e9a1c5f2
Revises: f4a6c8e2d1b3
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = "b7d3e9a1c5f2"
down_revision = "f4a6c8e2d1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "founding_testers",
        sa.Column(
            "number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "steam_id",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "premium_days",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.CheckConstraint(
            "number BETWEEN 1 AND 10",
            name="ck_founding_testers_number",
        ),
        sa.CheckConstraint(
            "premium_days >= 0",
            name="ck_founding_testers_premium_days",
        ),
        sa.ForeignKeyConstraint(
            ["steam_id"],
            ["users.steam_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "number",
        ),
    )

    op.create_index(
        op.f(
            "ix_founding_testers_steam_id"
        ),
        "founding_testers",
        ["steam_id"],
        unique=True,
    )

    founding_testers = sa.table(
        "founding_testers",
        sa.column(
            "number",
            sa.Integer(),
        ),
        sa.column(
            "premium_days",
            sa.Integer(),
        ),
    )

    op.bulk_insert(
        founding_testers,
        [
            {
                "number": number,
                "premium_days": 30,
            }
            for number in range(1, 11)
        ],
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_founding_testers_steam_id"
        ),
        table_name="founding_testers",
    )

    op.drop_table(
        "founding_testers"
    )

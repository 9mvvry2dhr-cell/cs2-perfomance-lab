"""add site visitors

Revision ID: f4a6c8e2d1b3
Revises: d2e4f6a8c1b3
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a6c8e2d1b3"
down_revision = "d2e4f6a8c1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_visitors",
        sa.Column(
            "visitor_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "visitor_id"
        ),
    )

    op.create_index(
        "ix_site_visitors_last_seen_at",
        "site_visitors",
        ["last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_visitors_last_seen_at",
        table_name="site_visitors",
    )

    op.drop_table(
        "site_visitors"
    )

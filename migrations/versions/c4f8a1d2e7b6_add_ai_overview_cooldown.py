"""add AI overview cooldown and cache

Revision ID: c4f8a1d2e7b6
Revises: 7c1f8a2d4e91
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f8a1d2e7b6"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "7c1f8a2d4e91"

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
    op.add_column(
        "users",
        sa.Column(
            "ai_overview_last_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "ai_overview_last_response",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "ai_overview_last_response",
    )

    op.drop_column(
        "users",
        "ai_overview_last_generated_at",
    )

"""cache per-match AI explanations

Revision ID: f7a3d9c2b1e4
Revises: c4f8a1d2e7b6
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a3d9c2b1e4"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "c4f8a1d2e7b6"

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
        "user_matches",
        sa.Column(
            "ai_explanation_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "user_matches",
        sa.Column(
            "ai_explanation_version",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.add_column(
        "user_matches",
        sa.Column(
            "ai_explanation_response",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "user_matches",
        "ai_explanation_response",
    )

    op.drop_column(
        "user_matches",
        "ai_explanation_version",
    )

    op.drop_column(
        "user_matches",
        "ai_explanation_generated_at",
    )

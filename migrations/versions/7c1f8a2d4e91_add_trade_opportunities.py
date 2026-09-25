"""add trade opportunities

Revision ID: 7c1f8a2d4e91
Revises: 3b7e1d9a4c20
Create Date: 2026-09-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c1f8a2d4e91"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "3b7e1d9a4c20"

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
    # Nullable intentionally: old demos are deleted after analysis,
    # so historical opportunities cannot be reconstructed honestly.
    op.add_column(
        "match_players",
        sa.Column(
            "trade_opportunities",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "match_players",
        "trade_opportunities",
    )

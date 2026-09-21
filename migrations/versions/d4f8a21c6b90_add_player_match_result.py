"""add player match result

Revision ID: d4f8a21c6b90
Revises: b81c2d4e9a70
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f8a21c6b90"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b81c2d4e9a70"

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
        "match_players",
        sa.Column(
            "result",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )

    op.create_check_constraint(
        "ck_match_players_result",
        "match_players",
        "result IN ('win', 'loss', 'draw', 'unknown')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_match_players_result",
        "match_players",
        type_="check",
    )

    op.drop_column(
        "match_players",
        "result",
    )

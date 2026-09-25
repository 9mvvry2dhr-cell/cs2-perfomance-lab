"""add clutch attempts

Revision ID: 3b7e1d9a4c20
Revises: e1f7c9a2b5d4
Create Date: 2026-09-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3b7e1d9a4c20"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "e1f7c9a2b5d4"

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
    # Nullable on purpose: existing persisted matches were analyzed
    # before clutch opportunities were tracked and cannot be rebuilt
    # because raw .dem files are deleted after analysis.
    op.add_column(
        "match_players",
        sa.Column(
            "clutch_attempts",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "match_players",
        "clutch_attempts",
    )

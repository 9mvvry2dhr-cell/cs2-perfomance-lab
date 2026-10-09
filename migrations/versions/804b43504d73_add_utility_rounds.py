"""add utility rounds

Revision ID: 804b43504d73
Revises: e1c9a4b7d2f6
Create Date: 2026-10-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "804b43504d73"
down_revision: Union[str, None] = "e1c9a4b7d2f6"
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
            "utility_rounds",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "'[]'"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "match_players",
        "utility_rounds",
    )

"""add findings version

Revision ID: 4b7d9e2a6c31
Revises: 1d3f4c8b7a12
Create Date: 2026-09-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b7d9e2a6c31"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "1d3f4c8b7a12"

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
    # Existing rows were created before explicit findings
    # versioning existed. Mark them as legacy first.
    op.add_column(
        "matches",
        sa.Column(
            "findings_version",
            sa.String(length=16),
            nullable=False,
            server_default="legacy",
        ),
    )

    # New writes must explicitly provide a version.
    op.alter_column(
        "matches",
        "findings_version",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "matches",
        "findings_version",
    )

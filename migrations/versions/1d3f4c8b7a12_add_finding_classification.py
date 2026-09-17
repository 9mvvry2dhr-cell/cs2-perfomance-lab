"""add finding classification

Revision ID: 1d3f4c8b7a12
Revises: 7061b8532626
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1d3f4c8b7a12"
down_revision: Union[str, Sequence[str], None] = "7061b8532626"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="weakness",
        ),
    )

    op.add_column(
        "findings",
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default="medium",
        ),
    )

    op.create_check_constraint(
        "ck_findings_kind",
        "findings",
        "kind IN ('strength', 'weakness')",
    )

    op.create_check_constraint(
        "ck_findings_severity",
        "findings",
        "severity IN ('low', 'medium', 'high')",
    )

    op.alter_column(
        "findings",
        "kind",
        server_default=None,
    )

    op.alter_column(
        "findings",
        "severity",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_findings_severity",
        "findings",
        type_="check",
    )

    op.drop_constraint(
        "ck_findings_kind",
        "findings",
        type_="check",
    )

    op.drop_column(
        "findings",
        "severity",
    )

    op.drop_column(
        "findings",
        "kind",
    )

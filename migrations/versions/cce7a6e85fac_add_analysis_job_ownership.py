"""add analysis job ownership

Revision ID: cce7a6e85fac
Revises: 9e7f1c2a4b88
Create Date: 2026-09-20 20:51:14.372583
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cce7a6e85fac"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9e7f1c2a4b88"

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
        "analysis_jobs",
        sa.Column(
            "owner_steam_id",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_analysis_jobs_owner_steam_id_users",
        "analysis_jobs",
        "users",
        ["owner_steam_id"],
        ["steam_id"],
        ondelete="SET NULL",
    )

    op.create_index(
        op.f(
            "ix_analysis_jobs_owner_steam_id"
        ),
        "analysis_jobs",
        ["owner_steam_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_analysis_jobs_owner_steam_id"
        ),
        table_name="analysis_jobs",
    )

    op.drop_constraint(
        "fk_analysis_jobs_owner_steam_id_users",
        "analysis_jobs",
        type_="foreignkey",
    )

    op.drop_column(
        "analysis_jobs",
        "owner_steam_id",
    )

"""enforce one active analysis job per owner

Revision ID: b81c2d4e9a70
Revises: cce7a6e85fac
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b81c2d4e9a70"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "cce7a6e85fac"

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


INDEX_NAME = (
    "uq_analysis_jobs_active_owner"
)

ACTIVE_PREDICATE = (
    "owner_steam_id IS NOT NULL "
    "AND status IN ('queued', 'processing')"
)


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "analysis_jobs",
        ["owner_steam_id"],
        unique=True,
        postgresql_where=sa.text(
            ACTIVE_PREDICATE
        ),
        sqlite_where=sa.text(
            ACTIVE_PREDICATE
        ),
    )


def downgrade() -> None:
    op.drop_index(
        INDEX_NAME,
        table_name="analysis_jobs",
    )

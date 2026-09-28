"""add match source

Revision ID: a9c2e4f6b8d1
Revises: f7a3d9c2b1e4
Create Date: 2026-09-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9c2e4f6b8d1"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "f7a3d9c2b1e4"

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
            "match_source",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_check_constraint(
        "ck_analysis_jobs_match_source",
        "analysis_jobs",
        "match_source IN "
        "('premier', 'faceit', 'unknown')",
    )

    op.add_column(
        "user_matches",
        sa.Column(
            "match_source",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_check_constraint(
        "ck_user_matches_match_source",
        "user_matches",
        "match_source IN "
        "('premier', 'faceit', 'unknown')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_matches_match_source",
        "user_matches",
        type_="check",
    )
    op.drop_column(
        "user_matches",
        "match_source",
    )

    op.drop_constraint(
        "ck_analysis_jobs_match_source",
        "analysis_jobs",
        type_="check",
    )
    op.drop_column(
        "analysis_jobs",
        "match_source",
    )

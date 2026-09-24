"""add bug reports

Revision ID: e1f7c9a2b5d4
Revises: a6c4e2f91b70
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f7c9a2b5d4"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a6c4e2f91b70"

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
    op.create_table(
        "bug_reports",
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "owner_steam_id",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            sa.String(length=36),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["owner_steam_id"],
            ["users.steam_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.match_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["analysis_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_bug_reports",
        ),
        sa.CheckConstraint(
            "category IN "
            "('analysis', 'statistics', 'ai', 'ui', 'other')",
            name="ck_bug_reports_category",
        ),
    )

    op.create_index(
        "ix_bug_reports_owner_steam_id",
        "bug_reports",
        ["owner_steam_id"],
    )

    op.create_index(
        "ix_bug_reports_match_id",
        "bug_reports",
        ["match_id"],
    )

    op.create_index(
        "ix_bug_reports_job_id",
        "bug_reports",
        ["job_id"],
    )

    op.create_index(
        "ix_bug_reports_created_at",
        "bug_reports",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bug_reports_created_at",
        table_name="bug_reports",
    )

    op.drop_index(
        "ix_bug_reports_job_id",
        table_name="bug_reports",
    )

    op.drop_index(
        "ix_bug_reports_match_id",
        table_name="bug_reports",
    )

    op.drop_index(
        "ix_bug_reports_owner_steam_id",
        table_name="bug_reports",
    )

    op.drop_table(
        "bug_reports",
    )

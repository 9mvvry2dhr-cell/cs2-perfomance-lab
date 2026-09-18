"""add auth users and sessions

Revision ID: 9e7f1c2a4b88
Revises: 4b7d9e2a6c31
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9e7f1c2a4b88"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "4b7d9e2a6c31"

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
        "users",
        sa.Column(
            "steam_id",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "steam_id"
        ),
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "steam_id",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            [
                "steam_id"
            ],
            [
                "users.steam_id"
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "token_hash"
        ),
    )

    op.create_index(
        op.f(
            "ix_auth_sessions_token_hash"
        ),
        "auth_sessions",
        [
            "token_hash"
        ],
        unique=True,
    )

    op.create_index(
        op.f(
            "ix_auth_sessions_steam_id"
        ),
        "auth_sessions",
        [
            "steam_id"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_auth_sessions_expires_at"
        ),
        "auth_sessions",
        [
            "expires_at"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_auth_sessions_revoked_at"
        ),
        "auth_sessions",
        [
            "revoked_at"
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_auth_sessions_revoked_at"
        ),
        table_name="auth_sessions",
    )

    op.drop_index(
        op.f(
            "ix_auth_sessions_expires_at"
        ),
        table_name="auth_sessions",
    )

    op.drop_index(
        op.f(
            "ix_auth_sessions_steam_id"
        ),
        table_name="auth_sessions",
    )

    op.drop_index(
        op.f(
            "ix_auth_sessions_token_hash"
        ),
        table_name="auth_sessions",
    )

    op.drop_table(
        "auth_sessions"
    )

    op.drop_table(
        "users"
    )

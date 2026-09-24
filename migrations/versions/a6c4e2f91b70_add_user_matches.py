"""add user matches

Revision ID: a6c4e2f91b70
Revises: d4f8a21c6b90
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c4e2f91b70"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "d4f8a21c6b90"

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
        "user_matches",
        sa.Column(
            "owner_steam_id",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "player_position",
            sa.Integer(),
            nullable=False,
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
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "owner_steam_id",
            "match_id",
            name="pk_user_matches",
        ),
        sa.UniqueConstraint(
            "match_id",
            "player_position",
            name="uq_user_matches_match_position",
        ),
        sa.CheckConstraint(
            "player_position >= 0",
            name="ck_user_matches_player_position",
        ),
    )

    op.create_index(
        "ix_user_matches_match_id",
        "user_matches",
        ["match_id"],
    )

    op.create_index(
        "ix_user_matches_created_at",
        "user_matches",
        ["created_at"],
    )

    # Existing completed analysis jobs already tell us:
    #
    # owner Steam ID
    #     -> match_id
    #     -> matching row in match_players
    #     -> player position
    #
    # Preserve the earliest known ownership timestamp if duplicate
    # historical completed jobs exist.
    op.execute(
        sa.text(
            """
            INSERT INTO user_matches (
                owner_steam_id,
                match_id,
                player_position,
                created_at
            )
            SELECT
                aj.owner_steam_id,
                aj.match_id,
                mp.position,
                MIN(aj.created_at)
            FROM analysis_jobs AS aj
            JOIN match_players AS mp
              ON mp.match_id = aj.match_id
             AND mp.steam_id = aj.owner_steam_id
            WHERE aj.status = 'completed'
              AND aj.owner_steam_id IS NOT NULL
              AND aj.match_id IS NOT NULL
            GROUP BY
                aj.owner_steam_id,
                aj.match_id,
                mp.position
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_matches_created_at",
        table_name="user_matches",
    )

    op.drop_index(
        "ix_user_matches_match_id",
        table_name="user_matches",
    )

    op.drop_table(
        "user_matches",
    )

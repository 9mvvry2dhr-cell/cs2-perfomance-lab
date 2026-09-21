"""add player match result

Revision ID: d4f8a21c6b90
Revises: b81c2d4e9a70
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f8a21c6b90"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b81c2d4e9a70"

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
            "result",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )

    op.create_check_constraint(
        "ck_match_players_result",
        "match_players",
        "result IN ('win', 'loss', 'draw', 'unknown')",
    )

    # Backfill only regulation MR12 matches where the player's
    # side counts prove the final side without guessing.
    #
    # For 13-23 round matches, a full-participation player has
    # exactly 12 rounds on the starting side and the remaining
    # rounds on the final side. Full 24-round matches are left
    # unknown because 12/12 alone cannot identify the final side.
    op.execute(
        sa.text(
            """
            UPDATE match_players AS mp
            SET result = CASE
                WHEN m.score_ct = m.score_t
                    THEN 'draw'
                WHEN (
                    CASE
                        WHEN ct.rounds_played = 12
                             AND t.rounds_played = m.rounds_played - 12
                            THEN 'T'
                        WHEN t.rounds_played = 12
                             AND ct.rounds_played = m.rounds_played - 12
                            THEN 'CT'
                        ELSE NULL
                    END
                ) = m.winner_side
                    THEN 'win'
                ELSE 'loss'
            END
            FROM matches AS m,
                 player_side_stats AS ct,
                 player_side_stats AS t
            WHERE mp.match_id = m.match_id
              AND ct.match_player_id = mp.id
              AND ct.side = 'CT'
              AND t.match_player_id = mp.id
              AND t.side = 'T'
              AND m.rounds_played BETWEEN 13 AND 23
              AND ct.rounds_played + t.rounds_played = m.rounds_played
              AND (
                    (
                        ct.rounds_played = 12
                        AND t.rounds_played = m.rounds_played - 12
                    )
                    OR
                    (
                        t.rounds_played = 12
                        AND ct.rounds_played = m.rounds_played - 12
                    )
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_match_players_result",
        "match_players",
        type_="check",
    )

    op.drop_column(
        "match_players",
        "result",
    )

"""add round state analytics

Revision ID: c8e4f1a2d7b6
Revises: b7d3e9a1c5f2
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "c8e4f1a2d7b6"
down_revision = "b7d3e9a1c5f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "round_advantages",
        sa.Column(
            "match_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "round_num",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "winner_team",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "first_advantage_team",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "first_advantage_tick",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "first_advantage_player_position",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "converted_first_advantage",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "advantage_lost",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "advantage_restored",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "comeback_team",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "max_t_advantage",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "max_ct_advantage",
            sa.Integer(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.match_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "match_id",
            "round_num",
        ),
        sa.CheckConstraint(
            "round_num >= 1",
            name="ck_round_advantages_round_num",
        ),
        sa.CheckConstraint(
            "winner_team IN (2, 3)",
            name="ck_round_advantages_winner_team",
        ),
        sa.CheckConstraint(
            "first_advantage_team IS NULL "
            "OR first_advantage_team IN (2, 3)",
            name="ck_round_advantages_first_team",
        ),
        sa.CheckConstraint(
            "comeback_team IS NULL "
            "OR comeback_team IN (2, 3)",
            name="ck_round_advantages_comeback_team",
        ),
        sa.CheckConstraint(
            "first_advantage_player_position IS NULL "
            "OR first_advantage_player_position >= 0",
            name="ck_round_advantages_player_position",
        ),
        sa.CheckConstraint(
            "max_t_advantage >= 0",
            name="ck_round_advantages_max_t",
        ),
        sa.CheckConstraint(
            "max_ct_advantage >= 0",
            name="ck_round_advantages_max_ct",
        ),
    )

    op.create_index(
        "ix_round_advantages_match_id",
        "round_advantages",
        ["match_id"],
    )

    op.create_table(
        "round_state_transitions",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "round_num",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "tick",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "attacker_position",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "victim_position",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "attacker_team",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "victim_team",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "cause",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "t_alive_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "ct_alive_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "t_alive_after",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "ct_alive_after",
            sa.Integer(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.match_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "match_id",
            "round_num",
            "position",
            name="uq_round_state_match_round_position",
        ),
        sa.CheckConstraint(
            "round_num >= 1",
            name="ck_round_state_round_num",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_round_state_position",
        ),
        sa.CheckConstraint(
            "tick >= 0",
            name="ck_round_state_tick",
        ),
        sa.CheckConstraint(
            "attacker_position IS NULL "
            "OR attacker_position >= 0",
            name="ck_round_state_attacker_position",
        ),
        sa.CheckConstraint(
            "victim_position IS NULL "
            "OR victim_position >= 0",
            name="ck_round_state_victim_position",
        ),
        sa.CheckConstraint(
            "attacker_team IS NULL "
            "OR attacker_team IN (2, 3)",
            name="ck_round_state_attacker_team",
        ),
        sa.CheckConstraint(
            "victim_team IN (2, 3)",
            name="ck_round_state_victim_team",
        ),
        sa.CheckConstraint(
            "cause IN "
            "('enemy', 'world', 'suicide', "
            "'teamkill', 'unknown')",
            name="ck_round_state_cause",
        ),
        sa.CheckConstraint(
            "t_alive_before >= 0 "
            "AND ct_alive_before >= 0 "
            "AND t_alive_after >= 0 "
            "AND ct_alive_after >= 0",
            name="ck_round_state_alive_counts",
        ),
    )

    op.create_index(
        "ix_round_state_transitions_match_id",
        "round_state_transitions",
        ["match_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_round_state_transitions_match_id",
        table_name="round_state_transitions",
    )

    op.drop_table(
        "round_state_transitions"
    )

    op.drop_index(
        "ix_round_advantages_match_id",
        table_name="round_advantages",
    )

    op.drop_table(
        "round_advantages"
    )

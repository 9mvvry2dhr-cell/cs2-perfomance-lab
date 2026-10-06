"""add turning analysis

Revision ID: d4f7b2c9a1e6
Revises: c8e4f1a2d7b6
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa


revision = "d4f7b2c9a1e6"
down_revision = "c8e4f1a2d7b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_flow",
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
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "winner_side",
            sa.String(length=4),
            nullable=False,
        ),
        sa.Column(
            "score_a_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "score_b_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "score_a_after",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "score_b_after",
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
            name="ck_match_flow_round_num",
        ),
        sa.CheckConstraint(
            "winner_team IN ('team_a', 'team_b')",
            name="ck_match_flow_winner_team",
        ),
        sa.CheckConstraint(
            "winner_side IN ('T', 'CT')",
            name="ck_match_flow_winner_side",
        ),
        sa.CheckConstraint(
            "score_a_before >= 0 "
            "AND score_b_before >= 0 "
            "AND score_a_after >= 0 "
            "AND score_b_after >= 0",
            name="ck_match_flow_scores",
        ),
    )

    op.create_index(
        "ix_match_flow_match_id",
        "match_flow",
        ["match_id"],
    )

    op.create_table(
        "turning_rounds",
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
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "swing_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "score_a_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "score_b_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "score_a_after",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "score_b_after",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "opponent_streak_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "winner_run_length",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "reasons",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "resolution",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "decisive_tick",
            sa.Integer(),
            nullable=True,
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
            name="ck_turning_rounds_round_num",
        ),
        sa.CheckConstraint(
            "winner_team IN ('team_a', 'team_b')",
            name="ck_turning_rounds_winner_team",
        ),
        sa.CheckConstraint(
            "swing_type IN ("
            "'no_advantage', "
            "'clean_conversion', "
            "'regained', "
            "'comeback', "
            "'stolen', "
            "'swing'"
            ")",
            name="ck_turning_rounds_swing_type",
        ),
        sa.CheckConstraint(
            "score_a_before >= 0 "
            "AND score_b_before >= 0 "
            "AND score_a_after >= 0 "
            "AND score_b_after >= 0",
            name="ck_turning_rounds_scores",
        ),
        sa.CheckConstraint(
            "opponent_streak_before >= 0",
            name="ck_turning_rounds_opponent_streak",
        ),
        sa.CheckConstraint(
            "winner_run_length >= 1",
            name="ck_turning_rounds_run_length",
        ),
        sa.CheckConstraint(
            "resolution IN ("
            "'sustained_control', "
            "'final_elimination', "
            "'unresolved'"
            ")",
            name="ck_turning_rounds_resolution",
        ),
        sa.CheckConstraint(
            "decisive_tick IS NULL "
            "OR decisive_tick >= 0",
            name="ck_turning_rounds_decisive_tick",
        ),
    )

    op.create_index(
        "ix_turning_rounds_match_id",
        "turning_rounds",
        ["match_id"],
    )

    op.create_table(
        "turning_control_events",
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
            "round_state_position",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "decisive",
            sa.Boolean(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.match_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "match_id",
                "round_num",
                "round_state_position",
            ],
            [
                "round_state_transitions.match_id",
                "round_state_transitions.round_num",
                "round_state_transitions.position",
            ],
            deferrable=True,
            initially="DEFERRED",
            name=(
                "fk_turning_control_"
                "round_state_transition"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "match_id",
            "round_num",
            "position",
            name=(
                "uq_turning_control_"
                "match_round_position"
            ),
        ),
        sa.CheckConstraint(
            "round_num >= 1",
            name="ck_turning_control_round_num",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_turning_control_position",
        ),
        sa.CheckConstraint(
            "round_state_position >= 0",
            name=(
                "ck_turning_control_"
                "round_state_position"
            ),
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'control_gain', "
            "'control_loss', "
            "'reversal', "
            "'equalizer'"
            ")",
            name="ck_turning_control_event_type",
        ),
    )

    op.create_index(
        "ix_turning_control_events_match_id",
        "turning_control_events",
        ["match_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_turning_control_events_match_id",
        table_name="turning_control_events",
    )

    op.drop_table(
        "turning_control_events"
    )

    op.drop_index(
        "ix_turning_rounds_match_id",
        table_name="turning_rounds",
    )

    op.drop_table(
        "turning_rounds"
    )

    op.drop_index(
        "ix_match_flow_match_id",
        table_name="match_flow",
    )

    op.drop_table(
        "match_flow"
    )

"""add match facts

Revision ID: b91e6c2a4f70
Revises: 804b43504d73
"""

from alembic import op
import sqlalchemy as sa


revision = "b91e6c2a4f70"
down_revision = "804b43504d73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_facts",
        sa.Column(
            "match_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "facts_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "capabilities",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.LargeBinary(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),
        sa.CheckConstraint(
            "facts_version >= 1",
            name="ck_match_facts_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.match_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "match_id"
        ),
    )


def downgrade() -> None:
    op.drop_table(
        "match_facts"
    )

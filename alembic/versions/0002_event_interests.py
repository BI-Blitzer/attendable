"""Add event_interests table for user interest tracking.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    interest_status_enum = sa.Enum(
        "noted", "interested", "attending",
        name="interest_status_enum",
    )
    op.create_table(
        "event_interests",
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", interest_status_enum, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("event_interests")
    if op.get_context().dialect.name != "sqlite":
        sa.Enum(name="interest_status_enum").drop(op.get_bind())

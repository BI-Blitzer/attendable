"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    event_source_enum = sa.Enum(
        "eventbrite", "meetup", "luma", "web_search", "manual",
        name="event_source_enum",
    )
    event_type_enum = sa.Enum("virtual", "physical", "hybrid", name="event_type_enum")
    cost_type_enum = sa.Enum("free", "paid", name="cost_type_enum")
    tag_type_enum = sa.Enum("industry", "technology", "general", name="tag_type_enum")

    # companies
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_normalized", sa.String(255), nullable=False, unique=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("linkedin_url", sa.String(512), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_companies_name_normalized", "companies", ["name_normalized"])

    # people
    op.create_table(
        "people",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=True,
        ),
        sa.Column("linkedin_url", sa.String(512), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # tags
    op.create_table(
        "tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("tag_type", tag_type_enum, nullable=False),
    )

    # events
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(255), nullable=False, index=True),
        sa.Column("source", event_source_enum, nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("event_type", event_type_enum, nullable=True),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("venue_name", sa.String(255), nullable=True),
        sa.Column("address", sa.String(512), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("state", sa.String(64), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("distance_miles", sa.Float, nullable=True),
        sa.Column("registration_url", sa.String(1024), nullable=True),
        sa.Column("event_url", sa.String(1024), nullable=False),
        sa.Column("cost_type", cost_type_enum, nullable=True),
        sa.Column("cost_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "canonical_event_id",
            sa.String(36),
            sa.ForeignKey("events.id"),
            nullable=True,
        ),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("source", "source_id", name="uq_event_source"),
    )

    # Junction tables
    op.create_table(
        "event_organizers",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "event_sponsors",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "event_speakers",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(128), nullable=True),
    )

    op.create_table(
        "event_tags",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.String(36), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("event_tags")
    op.drop_table("event_speakers")
    op.drop_table("event_sponsors")
    op.drop_table("event_organizers")
    op.drop_table("events")
    op.drop_table("tags")
    op.drop_table("people")
    op.drop_table("companies")
    if op.get_context().dialect.name != "sqlite":
        sa.Enum(name="cost_type_enum").drop(op.get_bind())
        sa.Enum(name="event_type_enum").drop(op.get_bind())
        sa.Enum(name="event_source_enum").drop(op.get_bind())
        sa.Enum(name="tag_type_enum").drop(op.get_bind())

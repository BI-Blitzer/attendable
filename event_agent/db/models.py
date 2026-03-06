"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EventSource(str, enum.Enum):
    eventbrite = "eventbrite"
    meetup = "meetup"
    luma = "luma"
    web_search = "web_search"
    manual = "manual"


class EventType(str, enum.Enum):
    virtual = "virtual"
    physical = "physical"
    hybrid = "hybrid"


class CostType(str, enum.Enum):
    free = "free"
    paid = "paid"


class TagType(str, enum.Enum):
    industry = "industry"
    technology = "technology"
    general = "general"


class InterestStatus(str, enum.Enum):
    noted = "noted"           # seen it, not interested
    interested = "interested" # want to look into it
    attending = "attending"   # confirmed going


# ---------------------------------------------------------------------------
# Junction tables (plain Table objects to avoid FK complexity)
# ---------------------------------------------------------------------------

from sqlalchemy import Table, Column

event_organizers = Table(
    "event_organizers",
    Base.metadata,
    Column("event_id", Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("company_id", Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
)

event_sponsors = Table(
    "event_sponsors",
    Base.metadata,
    Column("event_id", Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("company_id", Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
)

event_tags = Table(
    "event_tags",
    Base.metadata,
    Column("event_id", Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Uuid(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(512))
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    people: Mapped[list["Person"]] = relationship("Person", back_populates="company")
    organized_events: Mapped[list["Event"]] = relationship(
        "Event", secondary=event_organizers, back_populates="organizers"
    )
    sponsored_events: Mapped[list["Event"]] = relationship(
        "Event", secondary=event_sponsors, back_populates="sponsors"
    )


class Person(Base):
    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company | None"] = relationship("Company", back_populates="people")
    speaker_roles: Mapped[list["EventSpeaker"]] = relationship("EventSpeaker", back_populates="person")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tag_type: Mapped[TagType] = mapped_column(
        Enum(TagType, name="tag_type_enum"), nullable=False, default=TagType.general
    )

    events: Mapped[list["Event"]] = relationship("Event", secondary=event_tags, back_populates="tags")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_event_source"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[EventSource] = mapped_column(
        Enum(EventSource, name="event_source_enum"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[EventType | None] = mapped_column(
        Enum(EventType, name="event_type_enum"), nullable=True
    )

    start_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str | None] = mapped_column(String(64))

    venue_name: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(512))
    city: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(64))
    zip_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(64))

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    distance_miles: Mapped[float | None] = mapped_column(Float)

    registration_url: Mapped[str | None] = mapped_column(String(1024))
    event_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    cost_type: Mapped[CostType | None] = mapped_column(
        Enum(CostType, name="cost_type_enum"), nullable=True
    )
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Canonical event for cross-source dedup
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id"), nullable=True
    )

    raw_data: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organizers: Mapped[list[Company]] = relationship(
        "Company", secondary=event_organizers, back_populates="organized_events"
    )
    sponsors: Mapped[list[Company]] = relationship(
        "Company", secondary=event_sponsors, back_populates="sponsored_events"
    )
    speakers: Mapped[list["EventSpeaker"]] = relationship("EventSpeaker", back_populates="event", cascade="all, delete-orphan")
    tags: Mapped[list[Tag]] = relationship("Tag", secondary=event_tags, back_populates="events")
    duplicates: Mapped[list["Event"]] = relationship("Event", foreign_keys=[canonical_event_id])
    interest: Mapped["EventInterest | None"] = relationship("EventInterest", uselist=False, cascade="all, delete-orphan")


class EventInterest(Base):
    __tablename__ = "event_interests"

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[InterestStatus] = mapped_column(
        Enum(InterestStatus, name="interest_status_enum"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventSpeaker(Base):
    __tablename__ = "event_speakers"

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(String(128))

    event: Mapped[Event] = relationship("Event", back_populates="speakers")
    person: Mapped[Person] = relationship("Person", back_populates="speaker_roles")

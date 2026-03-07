"""CRUD + deduplication logic for the event agent."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import and_, or_, select, update
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_agent.db.models import (
    Company,
    Event,
    EventInterest,
    EventSource,
    EventSpeaker,
    EventType,
    CostType,
    InterestStatus,
    Person,
    Tag,
    TagType,
    event_organizers,
    event_sponsors,
    event_tags,
)


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation/extra spaces — used as dedup key."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Company
    # ------------------------------------------------------------------

    async def get_or_create_company(
        self,
        name: str,
        website: str | None = None,
        linkedin_url: str | None = None,
    ) -> Company:
        normalized = _normalize_name(name)
        result = await self.session.execute(
            select(Company).where(Company.name_normalized == normalized)
        )
        company = result.scalar_one_or_none()
        if company is None:
            company = Company(
                id=uuid.uuid4(),
                name=name,
                name_normalized=normalized,
                website=website,
                linkedin_url=linkedin_url,
            )
            self.session.add(company)
            await self.session.flush()
        else:
            # Update optional fields if missing
            if website and not company.website:
                company.website = website
            if linkedin_url and not company.linkedin_url:
                company.linkedin_url = linkedin_url
        return company

    # ------------------------------------------------------------------
    # Person
    # ------------------------------------------------------------------

    async def get_or_create_person(
        self,
        name: str,
        title: str | None = None,
        company_id: uuid.UUID | None = None,
        linkedin_url: str | None = None,
        email: str | None = None,
    ) -> Person:
        # Try by linkedin_url first (most reliable)
        if linkedin_url:
            result = await self.session.execute(
                select(Person).where(Person.linkedin_url == linkedin_url)
            )
            person = result.scalar_one_or_none()
            if person:
                return person

        # Fallback: match by name + company
        result = await self.session.execute(
            select(Person).where(Person.name == name, Person.company_id == company_id)
        )
        person = result.scalar_one_or_none()
        if person is None:
            person = Person(
                id=uuid.uuid4(),
                name=name,
                title=title,
                company_id=company_id,
                linkedin_url=linkedin_url,
                email=email,
            )
            self.session.add(person)
            await self.session.flush()
        return person

    # ------------------------------------------------------------------
    # Tag
    # ------------------------------------------------------------------

    async def get_or_create_tag(self, name: str, tag_type: TagType = TagType.general) -> Tag:
        result = await self.session.execute(
            select(Tag).where(Tag.name == name.lower())
        )
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(id=uuid.uuid4(), name=name.lower(), tag_type=tag_type)
            self.session.add(tag)
            await self.session.flush()
        return tag

    # ------------------------------------------------------------------
    # Event upsert
    # ------------------------------------------------------------------

    async def upsert_event(self, data: dict[str, Any]) -> Event:
        """
        Insert or update an event keyed on (source, source_id).
        data keys map to Event columns plus extra relation keys:
          organizer_data, sponsors_data, speakers_data,
          industry_tags, technology_tags
        """
        source = data["source"]
        source_id = data["source_id"]

        result = await self.session.execute(
            select(Event).where(Event.source == source, Event.source_id == source_id)
        )
        event = result.scalar_one_or_none()

        scalar_fields = {
            "title", "description", "event_type", "start_datetime", "end_datetime",
            "timezone", "venue_name", "address", "city", "state", "zip_code",
            "country", "latitude", "longitude", "distance_miles",
            "registration_url", "event_url", "cost_type", "cost_amount", "raw_data",
        }

        if event is None:
            event = Event(
                id=uuid.uuid4(),
                source=source,
                source_id=source_id,
            )
            self.session.add(event)

        for field in scalar_fields:
            if field in data and data[field] is not None:
                setattr(event, field, data[field])

        event.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

        # Relations
        await self._link_organizer(event, data.get("organizer_data"))
        await self._link_sponsors(event, data.get("sponsors_data", []))
        await self._link_speakers(event, data.get("speakers_data", []))
        await self._link_tags(event, data.get("industry_tags", []), TagType.industry)
        await self._link_tags(event, data.get("technology_tags", []), TagType.technology)

        await self.session.commit()

        # Cross-source dedup after commit
        await self._cross_source_dedup(event)

        return event

    async def _link_organizer(self, event: Event, organizer_data: dict | None):
        if not organizer_data or not organizer_data.get("name"):
            return
        company = await self.get_or_create_company(
            organizer_data["name"],
            organizer_data.get("website"),
            organizer_data.get("linkedin_url"),
        )
        exists = await self.session.execute(
            select(event_organizers).where(
                event_organizers.c.event_id == event.id,
                event_organizers.c.company_id == company.id,
            )
        )
        if not exists.first():
            await self.session.execute(
                insert(event_organizers).values(event_id=event.id, company_id=company.id)
            )

    async def _link_sponsors(self, event: Event, sponsors_data: list[dict]):
        for s in sponsors_data:
            if not s.get("name"):
                continue
            company = await self.get_or_create_company(
                s["name"], s.get("website"), s.get("linkedin_url")
            )
            exists = await self.session.execute(
                select(event_sponsors).where(
                    event_sponsors.c.event_id == event.id,
                    event_sponsors.c.company_id == company.id,
                )
            )
            if not exists.first():
                await self.session.execute(
                    insert(event_sponsors).values(event_id=event.id, company_id=company.id)
                )

    async def _link_speakers(self, event: Event, speakers_data: list[dict]):
        for sp in speakers_data:
            if not sp.get("name"):
                continue
            company = None
            if sp.get("company"):
                company = await self.get_or_create_company(sp["company"])
            person = await self.get_or_create_person(
                sp["name"],
                title=sp.get("title"),
                company_id=company.id if company else None,
                linkedin_url=sp.get("linkedin_url"),
            )
            # Upsert EventSpeaker
            result = await self.session.execute(
                select(EventSpeaker).where(
                    EventSpeaker.event_id == event.id,
                    EventSpeaker.person_id == person.id,
                )
            )
            if result.scalar_one_or_none() is None:
                self.session.add(
                    EventSpeaker(
                        event_id=event.id,
                        person_id=person.id,
                        role=sp.get("role"),
                    )
                )

    async def _link_tags(self, event: Event, tag_names: list[str], tag_type: TagType):
        for name in tag_names:
            if not name:
                continue
            tag = await self.get_or_create_tag(name, tag_type)
            exists = await self.session.execute(
                select(event_tags).where(
                    event_tags.c.event_id == event.id,
                    event_tags.c.tag_id == tag.id,
                )
            )
            if not exists.first():
                await self.session.execute(
                    insert(event_tags).values(event_id=event.id, tag_id=tag.id)
                )

    # ------------------------------------------------------------------
    # Cross-source deduplication
    # ------------------------------------------------------------------

    async def _cross_source_dedup(self, new_event: Event, threshold: float = 85.0):
        """
        Compare the new event against recent events from other sources.
        If fuzzy similarity on (title + date) > threshold, mark as duplicate.
        """
        if not new_event.start_datetime or not new_event.title:
            return

        # Fetch candidates from same day, different source
        date_str = new_event.start_datetime.date().isoformat()
        result = await self.session.execute(
            select(Event).where(
                Event.source != new_event.source,
                Event.canonical_event_id.is_(None),
                Event.id != new_event.id,
            )
        )
        candidates = result.scalars().all()

        for candidate in candidates:
            if not candidate.start_datetime:
                continue
            if candidate.start_datetime.date().isoformat() != date_str:
                continue
            score = fuzz.token_sort_ratio(new_event.title, candidate.title)
            if score >= threshold:
                # new_event is the duplicate; candidate is canonical
                await self.session.execute(
                    update(Event)
                    .where(Event.id == new_event.id)
                    .values(canonical_event_id=candidate.id)
                )
                await self.session.commit()
                break

    # ------------------------------------------------------------------
    # Classification check
    # ------------------------------------------------------------------

    async def get_classified_source_ids(
        self, pairs: list[tuple[str, str]]
    ) -> set[tuple[str, str]]:
        """
        Return the subset of (source, source_id) pairs that already exist in
        the database with a non-null event_type (i.e. already classified).
        """
        if not pairs:
            return set()
        conditions = [
            and_(Event.source == src, Event.source_id == sid)
            for src, sid in pairs
        ]
        result = await self.session.execute(
            select(Event.source, Event.source_id).where(
                Event.event_type.isnot(None),
                or_(*conditions),
            )
        )
        return {(row.source, row.source_id) for row in result}

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _apply_event_filters(
        self,
        q,
        search: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        max_distance_miles: float | None = None,
        free_only: bool = False,
        hide_noted: bool = True,
        interest_statuses: list[str] | None = None,
    ):
        if search:
            q = q.where(Event.title.ilike(f"%{search}%"))
        if event_type:
            q = q.where(Event.event_type == event_type)
        if source:
            q = q.where(Event.source == source)
        if from_date:
            q = q.where(Event.start_datetime >= from_date)
        if to_date:
            q = q.where(Event.start_datetime <= to_date)
        if max_distance_miles is not None:
            q = q.where(
                (Event.distance_miles <= max_distance_miles)
                | (Event.event_type == EventType.virtual)
            )
        if free_only:
            q = q.where(Event.cost_type == CostType.free)
        if tags:
            tag_sq = (
                select(event_tags.c.event_id)
                .join(Tag, Tag.id == event_tags.c.tag_id)
                .where(Tag.name.in_([t.lower() for t in tags]))
                .scalar_subquery()
            )
            q = q.where(Event.id.in_(tag_sq))
        if hide_noted:
            noted_ids = (
                select(EventInterest.event_id)
                .where(EventInterest.status == InterestStatus.noted)
                .scalar_subquery()
            )
            q = q.where(Event.id.notin_(noted_ids))
        if interest_statuses:
            interest_ids = (
                select(EventInterest.event_id)
                .where(EventInterest.status.in_(interest_statuses))
                .scalar_subquery()
            )
            q = q.where(Event.id.in_(interest_ids))
        return q

    async def list_events(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        max_distance_miles: float | None = None,
        free_only: bool = False,
        hide_noted: bool = True,
        interest_statuses: list[str] | None = None,
    ) -> list[Event]:
        q = (
            select(Event)
            .where(Event.canonical_event_id.is_(None))
            .options(selectinload(Event.tags), selectinload(Event.interest))
        )
        q = self._apply_event_filters(
            q, search, event_type, source, tags,
            from_date, to_date, max_distance_miles, free_only, hide_noted,
            interest_statuses,
        )
        q = q.order_by(Event.start_datetime.asc())
        q = q.offset((page - 1) * limit).limit(limit)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count_events(
        self,
        search: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        max_distance_miles: float | None = None,
        free_only: bool = False,
        hide_noted: bool = True,
        interest_statuses: list[str] | None = None,
    ) -> int:
        from sqlalchemy import func as _func  # noqa: PLC0415
        q = (
            select(_func.count())
            .select_from(Event)
            .where(Event.canonical_event_id.is_(None))
        )
        q = self._apply_event_filters(
            q, search, event_type, source, tags,
            from_date, to_date, max_distance_miles, free_only, hide_noted,
            interest_statuses,
        )
        result = await self.session.execute(q)
        return result.scalar_one()

    async def get_event(self, event_id: uuid.UUID) -> Event | None:
        result = await self.session.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Interest tracking
    # ------------------------------------------------------------------

    async def set_interest(self, event_id: uuid.UUID, status: str) -> None:
        result = await self.session.execute(
            select(EventInterest).where(EventInterest.event_id == event_id)
        )
        interest = result.scalar_one_or_none()
        if interest is None:
            self.session.add(EventInterest(event_id=event_id, status=InterestStatus(status)))
        else:
            interest.status = InterestStatus(status)
            interest.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def clear_interest(self, event_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(EventInterest).where(EventInterest.event_id == event_id)
        )
        interest = result.scalar_one_or_none()
        if interest:
            await self.session.delete(interest)
            await self.session.commit()

    # ------------------------------------------------------------------
    # Archival
    # ------------------------------------------------------------------

    async def list_tags_with_counts(self) -> list[dict]:
        from sqlalchemy import func  # noqa: PLC0415
        dismissed_ids = (
            select(EventInterest.event_id)
            .where(EventInterest.status == "noted")
            .scalar_subquery()
        )
        stmt = (
            select(Tag.name, Tag.tag_type, func.count(Event.id).label("count"))
            .outerjoin(event_tags, Tag.id == event_tags.c.tag_id)
            .outerjoin(Event, Event.id == event_tags.c.event_id)
            .where(
                (Event.id == None) |  # noqa: E711
                (Event.canonical_event_id.is_(None) & Event.id.not_in(dismissed_ids))
            )
            .group_by(Tag.id, Tag.name, Tag.tag_type)
            .order_by(func.count(Event.id).desc(), Tag.name)
        )
        result = await self.session.execute(stmt)
        return [{"name": r.name, "tag_type": r.tag_type, "count": r.count} for r in result]

    async def cleanup_past_events(self, days_past: int = 30) -> int:
        """
        Delete events whose date has passed by more than days_past days.
        Uses end_datetime when available, otherwise start_datetime.
        Returns the number of events deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_past)
        result = await self.session.execute(
            select(Event).where(
                or_(
                    and_(Event.end_datetime.isnot(None), Event.end_datetime < cutoff),
                    and_(Event.end_datetime.is_(None), Event.start_datetime.isnot(None), Event.start_datetime < cutoff),
                )
            )
        )
        events = result.scalars().all()
        for event in events:
            await self.session.delete(event)
        await self.session.commit()
        return len(events)
